"""Resilient Web3 gateway to the EvidenceRegistry contract.

API routes never construct or submit blockchain calls themselves; they go through
``blockchain_service``. Transaction hashes are returned in the format already stored
in PostgreSQL (lowercase hex without a ``0x`` prefix); use ``normalize_hex`` /
``hex_variants`` when comparing values that may carry a prefix.
"""
import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted, TransactionNotFound, Web3RPCError, Web3Exception

logger = logging.getLogger("secure_audit.blockchain")

SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
TX_HASH_HEX = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")
CUSTODY_ACTIONS = ("REGISTERED", "VERIFIED", "TRANSFERRED")
# Revert strings the contract uses for "not registered"; matched case-insensitively.
_NOT_REGISTERED_MARKERS = ("does not exist",)


class BlockchainUnavailable(RuntimeError):
    """The node, contract or ABI cannot be reached. Nothing was changed on-chain."""


class BlockchainTransactionError(RuntimeError):
    """A transaction was rejected, reverted or could not be confirmed."""


def is_sha256_hex(value: str | None) -> bool:
    return bool(value) and bool(SHA256_HEX.match(value))


def normalize_hex(value: Any) -> str:
    """Lowercase hex without a 0x prefix (the format stored in the database)."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    text = value.hex() if hasattr(value, "hex") and not isinstance(value, str) else str(value)
    text = text.strip().lower()
    return text[2:] if text.startswith("0x") else text


def hex_variants(value: str) -> list[str]:
    """Both stored spellings of a hash, for queries against legacy rows."""
    bare = normalize_hex(value)
    return [bare, "0x" + bare] if bare else []


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("Invalid integer for %s; using %s", name, default)
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass
class BlockchainConfig:
    """All blockchain settings, read once from the environment."""
    rpc_url: str = field(default_factory=lambda: os.getenv("ETHEREUM_RPC_URL", "http://127.0.0.1:8545"))
    rpc_timeout: int = field(default_factory=lambda: _env_int("BLOCKCHAIN_RPC_TIMEOUT_SECONDS", 15, 1))
    tx_timeout: int = field(default_factory=lambda: _env_int("BLOCKCHAIN_TX_TIMEOUT_SECONDS", 90, 5))
    retries: int = field(default_factory=lambda: _env_int("BLOCKCHAIN_RETRIES", 3, 1))
    confirmations: int = field(default_factory=lambda: _env_int("BLOCKCHAIN_CONFIRMATIONS", 0))
    private_key: str | None = field(default_factory=lambda: os.getenv("ETHEREUM_PRIVATE_KEY") or None)
    sender: str | None = field(default_factory=lambda: os.getenv("ETHEREUM_SENDER_ADDRESS") or None)
    auto_redeploy: bool = field(default_factory=lambda: _env_bool("BLOCKCHAIN_AUTO_REDEPLOY"))
    network_name: str = field(default_factory=lambda: os.getenv("BLOCKCHAIN_NETWORK_NAME", ""))


def _revert_reason(exc: Exception) -> str:
    message = getattr(exc, "message", None) or str(exc)
    match = re.search(r"revert(?:ed)?[:\s]+(.+)$", message, re.IGNORECASE)
    return (match.group(1) if match else message).strip().strip("'\"")[:200]


def _is_revert(exc: Exception) -> bool:
    return isinstance(exc, ContractLogicError) or "revert" in str(exc).lower()


def _is_not_registered(exc: Exception) -> bool:
    return any(marker in str(exc).lower() for marker in _NOT_REGISTERED_MARKERS)


def _utc(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, timezone.utc)


class EvidenceBlockchainService:
    def __init__(self, config: BlockchainConfig | None = None) -> None:
        self.config = config or BlockchainConfig()
        # Kept as attributes for scripts that read them directly.
        self.rpc_url = self.config.rpc_url
        self.timeout = self.config.tx_timeout
        self.retries = self.config.retries
        self.private_key = self.config.private_key
        self.sender = self.config.sender
        self._web3: Web3 | None = None
        self._contract = None
        self._runtime_address: str | None = None
        self._lock = threading.RLock()
        # Serialises nonce allocation + broadcast so concurrent requests never reuse a nonce.
        self._tx_lock = threading.Lock()
        root = Path(__file__).resolve().parents[2]
        self._artifact_path = Path(os.getenv("EVIDENCE_REGISTRY_ARTIFACT", root / "blockchain" / "artifacts" / "contracts" / "EvidenceRegistry.sol" / "EvidenceRegistry.json"))
        self._deployment_path = Path(os.getenv("EVIDENCE_REGISTRY_DEPLOYMENT", root / "blockchain" / "deployments" / "localhost.json"))

    # ------------------------------------------------------------------ connection

    def is_rpc_alive(self, timeout: float = 1.5) -> bool:
        """Fast TCP liveness check to avoid long socket hangs when the node is down."""
        try:
            parsed = urllib.parse.urlparse(self.rpc_url)
            with socket.create_connection((parsed.hostname or "127.0.0.1", parsed.port or 8545), timeout=timeout):
                return True
        except OSError:
            return False

    def _redeploy_if_needed(self) -> str:
        """Deploy a fresh registry via deploy.js (only when BLOCKCHAIN_AUTO_REDEPLOY is enabled)."""
        root = Path(__file__).resolve().parents[2]
        if not (root / "blockchain" / "scripts" / "deploy.js").is_file():
            return ""
        logger.warning("EvidenceRegistry not found on chain; auto-deploying because BLOCKCHAIN_AUTO_REDEPLOY is set")
        try:
            res = subprocess.run(["node", "scripts/deploy.js"], cwd=root / "blockchain", capture_output=True,
                                 text=True, timeout=60)
            if res.returncode == 0 and self._deployment_path.is_file():
                self._runtime_address = json.loads(self._deployment_path.read_text(encoding="utf-8"))["address"]
                logger.info("Auto-deployment successful: %s", self._runtime_address)
                return self._runtime_address
            logger.error("Auto-deployment failed: %s %s", res.stdout, res.stderr)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
            logger.error("Auto-deployment script execution failed: %s", exc)
        return ""

    def _contract_address(self) -> str:
        if self._runtime_address:
            return self._runtime_address
        configured = os.getenv("EVIDENCE_REGISTRY_ADDRESS")
        if configured:
            return configured
        if self._deployment_path.is_file():
            return json.loads(self._deployment_path.read_text(encoding="utf-8"))["address"]
        raise BlockchainUnavailable("EvidenceRegistry address is not configured. Deploy the contract or set EVIDENCE_REGISTRY_ADDRESS.")

    def _connect(self) -> None:
        with self._lock:
            if not self.is_rpc_alive(timeout=1.5):
                raise BlockchainUnavailable(f"Ethereum provider is unavailable at {self.rpc_url}")
            web3 = Web3(Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": self.config.rpc_timeout}))
            if not web3.is_connected():
                raise BlockchainUnavailable(f"Ethereum provider is unavailable at {self.rpc_url}")
            if not self._artifact_path.is_file():
                raise BlockchainUnavailable("EvidenceRegistry ABI artifact is unavailable; run Hardhat compile first.")
            artifact = json.loads(self._artifact_path.read_text(encoding="utf-8"))

            address = None
            try:
                address = Web3.to_checksum_address(self._contract_address())
                has_code = bool(web3.eth.get_code(address))
            except (ValueError, KeyError, OSError, Web3Exception, BlockchainUnavailable):
                has_code = False

            # Silently deploying a fresh, empty registry would orphan every existing
            # registration (all evidence would then fail verification), so automatic
            # redeployment is opt-in. Use the admin redeploy endpoint deliberately instead.
            if not has_code and self.config.auto_redeploy:
                redeploy_addr = self._redeploy_if_needed()
                if redeploy_addr:
                    address = Web3.to_checksum_address(redeploy_addr)
                    has_code = bool(web3.eth.get_code(address))

            if not has_code or not address:
                raise BlockchainUnavailable(
                    f"No EvidenceRegistry contract found at {address or 'the configured address'}. The blockchain node "
                    "was probably restarted without persistence, so existing registrations are gone. Automatic "
                    "redeployment is disabled (BLOCKCHAIN_AUTO_REDEPLOY=false); redeploy deliberately and re-run "
                    "backfill_blockchain_registration.py.")

            self._web3, self._contract = web3, web3.eth.contract(address=address, abi=artifact["abi"])
            logger.info("blockchain.connected chain_id=%s contract=%s", web3.eth.chain_id, address)

    def reload(self) -> None:
        self._web3 = self._contract = None
        if self._deployment_path.is_file():
            self._runtime_address = json.loads(self._deployment_path.read_text(encoding="utf-8"))["address"]
        self._connect()

    def _ready(self) -> tuple[Web3, Any]:
        try:
            if not self._web3 or not self._web3.is_connected() or not self._contract:
                self._connect()
            return self._web3, self._contract
        except Exception as exc:
            self._web3 = self._contract = None
            if isinstance(exc, BlockchainUnavailable):
                raise
            raise BlockchainUnavailable(str(exc)) from exc

    def _has_function(self, contract, name: str) -> bool:
        return any(item.get("type") == "function" and item.get("name") == name for item in contract.abi)

    def _has_event(self, contract, name: str) -> bool:
        return any(item.get("type") == "event" and item.get("name") == name for item in contract.abi)

    # ------------------------------------------------------------------ status / health

    def status(self) -> dict:
        try:
            if not self.is_rpc_alive(timeout=1.5):
                return {"connected": False, "error": f"Ethereum provider is unavailable at {self.rpc_url}"}
            web3, contract = self._ready()
            return {
                "connected": True,
                "chainId": web3.eth.chain_id,
                "contractAddress": contract.address,
                "latestBlock": web3.eth.block_number,
                "sender": self._sender(web3),
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def network_info(self) -> dict:
        """Connection validation for health checks and the ledger UI (read-only)."""
        started = time.perf_counter()
        base = {"connected": False, "rpcReachable": self.is_rpc_alive(timeout=1.5),
                "confirmationsRequired": self.config.confirmations}
        if not base["rpcReachable"]:
            return {**base, "error": "Blockchain node is unreachable"}
        try:
            web3, contract = self._ready()
            chain_id = web3.eth.chain_id
            sender = self._sender(web3)
            info = {
                **base,
                "connected": True,
                "network": self.config.network_name or ("Ganache (local)" if chain_id == 1337 else f"Chain {chain_id}"),
                "chainId": chain_id,
                "clientVersion": web3.client_version,
                "latestBlock": web3.eth.block_number,
                "gasPriceWei": web3.eth.gas_price,
                "contractAddress": contract.address,
                "contractDeployed": bool(web3.eth.get_code(contract.address)),
                "walletAddress": sender,
                "walletBalanceWei": web3.eth.get_balance(sender),
                "accessControlled": self._has_function(contract, "isRegistrar"),
            }
            if info["accessControlled"]:
                try:
                    info["walletAuthorised"] = bool(contract.functions.isRegistrar(sender).call())
                    info["totalRegistered"] = int(contract.functions.totalEvidence().call())
                except (ContractLogicError, Web3RPCError, Web3Exception, ValueError):
                    # The ABI is newer than the deployed contract (deployed before access
                    # control was added): it still works, it just has no registrar list.
                    info["accessControlled"] = False
            info["latencyMs"] = round((time.perf_counter() - started) * 1000, 1)
            return info
        except Exception as exc:
            return {**base, "error": str(exc)}

    def _sender(self, web3: Web3) -> str:
        if self.private_key:
            return web3.eth.account.from_key(self.private_key).address
        if self.sender:
            return Web3.to_checksum_address(self.sender)
        accounts = web3.eth.accounts
        if not accounts:
            raise BlockchainUnavailable("No sender account configured. Set ETHEREUM_SENDER_ADDRESS or ETHEREUM_PRIVATE_KEY.")
        return accounts[0]

    # ------------------------------------------------------------------ transactions

    def _transact(self, function) -> dict:
        """Send one contract transaction and wait for a confirmed receipt.

        Retries only when nothing was broadcast (node unreachable, RPC refused the
        request). A contract revert is deterministic and is never retried, and once a
        transaction has been broadcast it is never resent: a slow receipt is waited
        for, so a timeout cannot produce a second, duplicate transaction.
        """
        fn_name = getattr(function, "fn_name", str(function))
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                web3, contract = self._ready()
                sender = self._sender(web3)
                with self._tx_lock:
                    tx = function.build_transaction({
                        "from": sender,
                        "nonce": web3.eth.get_transaction_count(sender, "pending"),
                        "chainId": web3.eth.chain_id,
                    })
                    if self.private_key:
                        signed = web3.eth.account.sign_transaction(tx, self.private_key)
                        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
                    else:
                        tx_hash = web3.eth.send_transaction(tx)
            except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as exc:
                if _is_revert(exc):
                    reason = _revert_reason(exc)
                    logger.warning("blockchain.tx_rejected function=%s reason=%s", fn_name, reason)
                    raise BlockchainTransactionError(f"The smart contract rejected {fn_name}: {reason}") from exc
                last_error = exc
            except (OSError, BlockchainUnavailable) as exc:
                last_error = exc
            else:
                logger.info("blockchain.tx_sent function=%s tx=%s sender=%s attempt=%s",
                            fn_name, normalize_hex(tx_hash), sender, attempt)
                return self._await_receipt(web3, contract, tx_hash, fn_name)
            logger.warning("blockchain.tx_retry function=%s attempt=%s/%s error=%s", fn_name, attempt, self.retries, last_error)
            self._web3 = self._contract = None
            if attempt < self.retries:
                time.sleep(2 ** (attempt - 1))
        raise BlockchainUnavailable(f"Blockchain transaction {fn_name} failed after {self.retries} attempts: {last_error}")

    def _await_receipt(self, web3: Web3, contract, tx_hash, fn_name: str) -> dict:
        tx_hex = normalize_hex(tx_hash)
        try:
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.timeout, poll_latency=1)
        except TimeExhausted as exc:
            logger.error("blockchain.tx_unconfirmed function=%s tx=%s", fn_name, tx_hex)
            raise BlockchainTransactionError(
                f"Transaction 0x{tx_hex} was broadcast but not mined within {self.timeout}s. It was not resent; "
                "check it with GET /blockchain/transaction/{txHash} before retrying.") from exc
        if receipt.status != 1:
            logger.error("blockchain.tx_reverted function=%s tx=%s", fn_name, tx_hex)
            raise BlockchainTransactionError(f"Transaction reverted on chain: 0x{tx_hex}")
        confirmations = self._wait_for_confirmations(web3, receipt.blockNumber)
        block = web3.eth.get_block(receipt.blockNumber)
        logger.info("blockchain.tx_confirmed function=%s tx=%s block=%s gas_used=%s",
                    fn_name, tx_hex, receipt.blockNumber, receipt.gasUsed)
        return {
            "transactionHash": tx_hex,
            "blockNumber": receipt.blockNumber,
            "blockHash": normalize_hex(receipt.blockHash),
            "gasUsed": receipt.gasUsed,
            "contractAddress": receipt.to or contract.address,
            "from": receipt["from"],
            "chainId": web3.eth.chain_id,
            "status": "SUCCESS",
            "confirmations": confirmations,
            "timestamp": _utc(block["timestamp"]),
        }

    def _wait_for_confirmations(self, web3: Web3, block_number: int) -> int:
        """Block until BLOCKCHAIN_CONFIRMATIONS blocks sit on top of the receipt (0 = instant, Ganache)."""
        required = self.config.confirmations
        deadline = time.monotonic() + self.timeout
        while True:
            confirmations = web3.eth.block_number - block_number
            if confirmations >= required:
                return confirmations
            if time.monotonic() > deadline:
                raise BlockchainTransactionError(
                    f"Transaction in block {block_number} has {confirmations} of {required} required confirmations")
            time.sleep(1)

    # ------------------------------------------------------------------ evidence operations

    def register_evidence(self, evidence_id: str, case_id: str, file_name: str, sha256_hash: str, officer_id: str) -> dict:
        if not is_sha256_hex(sha256_hash):
            raise BlockchainTransactionError("sha256_hash must be 64 lowercase hexadecimal characters")
        if self.get_registration(evidence_id) is not None:
            raise BlockchainTransactionError("Evidence is already registered on-chain")
        _, contract = self._ready()
        return self._transact(contract.functions.registerEvidence(evidence_id, case_id, file_name, sha256_hash, officer_id))

    def verify_evidence(self, evidence_id: str, sha256_hash: str, officer_id: str) -> tuple[bool, dict]:
        if not is_sha256_hex(sha256_hash):
            raise BlockchainTransactionError("sha256_hash must be 64 lowercase hexadecimal characters")
        registration = self.get_registration(evidence_id)
        if registration is None:
            raise BlockchainTransactionError(f"Evidence '{evidence_id}' is not registered on the blockchain")
        stored_hash = registration["sha256Hash"]
        _, contract = self._ready()
        verification = self._transact(contract.functions.verifyEvidence(evidence_id, sha256_hash))
        # The verdict is the contract's own: the isMatch field of the EvidenceVerified
        # event emitted by this transaction.
        chain_is_match = self._verified_event_result(verification["transactionHash"])
        if chain_is_match is None:
            raise BlockchainTransactionError("Verification transaction emitted no EvidenceVerified event")
        if chain_is_match != (stored_hash == sha256_hash):
            raise BlockchainTransactionError("On-chain verification result disagrees with the registered hash")
        custody = self._transact(contract.functions.addCustodyRecord(evidence_id, officer_id, "VERIFIED"))
        verification["custodyTransaction"] = custody
        verification["onChainHash"] = stored_hash
        verification["chainIsMatch"] = chain_is_match
        verification["registration"] = registration
        return chain_is_match, verification

    def _verified_event_result(self, tx_hash: str) -> bool | None:
        web3, contract = self._ready()
        receipt = web3.eth.get_transaction_receipt("0x" + normalize_hex(tx_hash))
        from web3.logs import DISCARD
        events = contract.events.EvidenceVerified().process_receipt(receipt, errors=DISCARD)
        return bool(events[0]["args"]["isMatch"]) if events else None

    @property
    def contract_address(self) -> str:
        _, contract = self._ready()
        return contract.address

    def get_registration(self, evidence_id: str) -> dict | None:
        """On-chain registration record, or None when the ID is not registered."""
        _, contract = self._ready()
        try:
            record = contract.functions.getEvidence(evidence_id).call()
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as exc:
            if _is_not_registered(exc):
                return None
            raise BlockchainUnavailable(f"Could not read the on-chain registration: {exc}") from exc
        return {"evidenceId": record[0], "caseId": record[1], "fileName": record[2], "sha256Hash": record[3],
                "uploadedBy": record[4], "timestamp": _utc(record[5])}

    def find_registration_receipt(self, evidence_id: str) -> dict | None:
        """Receipt details of the transaction that registered ``evidence_id`` (read-only)."""
        web3, contract = self._ready()
        logs = contract.events.EvidenceRegistered().get_logs(from_block=0, argument_filters={"evidenceId": evidence_id})
        if not logs:
            return None
        return self._receipt_metadata(web3, contract, logs[0]["transactionHash"])

    def _receipt_metadata(self, web3: Web3, contract, tx_hash) -> dict:
        receipt = web3.eth.get_transaction_receipt(tx_hash)
        block = web3.eth.get_block(receipt.blockNumber)
        return {"transactionHash": normalize_hex(tx_hash), "blockNumber": receipt.blockNumber,
                "blockHash": normalize_hex(receipt.blockHash), "gasUsed": receipt.gasUsed,
                "contractAddress": receipt.to or contract.address, "from": receipt["from"],
                "chainId": web3.eth.chain_id, "status": "SUCCESS" if receipt.status == 1 else "FAILED",
                "timestamp": _utc(block["timestamp"])}

    def receipt_metadata(self, tx_hash: str) -> dict | None:
        """Receipt metadata for a stored transaction hash, or None if the chain does not know it."""
        web3, contract = self._ready()
        try:
            return self._receipt_metadata(web3, contract, "0x" + normalize_hex(tx_hash))
        except TransactionNotFound:
            return None

    def transaction_details(self, tx_hash: str) -> dict | None:
        """Everything the ledger UI shows in its transaction modal (read-only), or None if unknown."""
        if not TX_HASH_HEX.match(tx_hash or ""):
            raise ValueError("Transaction hash must be 64 hexadecimal characters")
        web3, contract = self._ready()
        prefixed = "0x" + normalize_hex(tx_hash)
        try:
            tx = web3.eth.get_transaction(prefixed)
        except TransactionNotFound:
            return None
        try:
            receipt = web3.eth.get_transaction_receipt(prefixed)
        except TransactionNotFound:
            receipt = None
        function_name, arguments = None, {}
        if tx.get("to") and normalize_hex(tx["to"]) == normalize_hex(contract.address):
            try:
                decoded, params = contract.decode_function_input(tx["input"])
                function_name, arguments = decoded.fn_name, {k: str(v) for k, v in params.items()}
            except ValueError:
                function_name = "unknown"
        events = []
        if receipt is not None:
            from web3.logs import DISCARD
            for item in contract.abi:
                if item.get("type") != "event":
                    continue
                for event in getattr(contract.events, item["name"])().process_receipt(receipt, errors=DISCARD):
                    args = {k: (normalize_hex(v) if isinstance(v, (bytes, bytearray)) else v)
                            for k, v in dict(event["args"]).items()}
                    # Indexed strings are stored as their keccak256 topic; show the plain
                    # evidence ID when it is the one passed to the call.
                    plain_id = arguments.get("evidenceId")
                    if plain_id and args.get("evidenceId") == normalize_hex(Web3.keccak(text=plain_id)):
                        args["evidenceId"] = plain_id
                    events.append({"name": event["event"], "args": args})
        latest = web3.eth.block_number
        block_number = tx.get("blockNumber")
        block = web3.eth.get_block(block_number) if block_number is not None else None
        return {
            "transactionHash": normalize_hex(tx["hash"]),
            "status": ("SUCCESS" if receipt.status == 1 else "FAILED") if receipt is not None else "PENDING",
            "blockNumber": block_number,
            "blockHash": normalize_hex(tx.get("blockHash")) or None,
            "timestamp": _utc(block["timestamp"]).isoformat() if block else None,
            "confirmations": (latest - block_number) if block_number is not None else 0,
            "from": tx["from"],
            "to": tx.get("to"),
            "nonce": tx["nonce"],
            "gasLimit": tx["gas"],
            "gasUsed": receipt.gasUsed if receipt is not None else None,
            "gasPriceWei": tx.get("gasPrice"),
            "effectiveGasPriceWei": receipt.get("effectiveGasPrice") if receipt is not None else None,
            "chainId": web3.eth.chain_id,
            "contractAddress": contract.address,
            "function": function_name,
            "arguments": arguments,
            "events": events,
        }

    def transfer_custody(self, evidence_id: str, officer_id: str) -> dict:
        _, contract = self._ready()
        return self._transact(contract.functions.addCustodyRecord(evidence_id, officer_id, "TRANSFERRED"))

    def custody_history(self, evidence_id: str) -> list[dict]:
        _, contract = self._ready()
        try:
            records = contract.functions.getCustodyHistory(evidence_id).call()
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as exc:
            if _is_not_registered(exc):
                return []
            raise BlockchainUnavailable(f"Could not read the on-chain custody history: {exc}") from exc
        return [{"officerId": item[0], "officer_id": item[0], "action": item[1], "timestamp": _utc(item[2]).isoformat()}
                for item in records]

    def recent_blocks(self, limit: int = 8) -> list[dict]:
        web3, _ = self._ready()
        latest = web3.eth.block_number
        blocks = []
        for number in range(latest, max(-1, latest - limit), -1):
            block = web3.eth.get_block(number)
            blocks.append({"number": number, "hash": normalize_hex(block["hash"]),
                           "timestamp": _utc(block["timestamp"]).isoformat(), "transactions": len(block["transactions"])})
        return blocks

    def events_since(self, from_block: int) -> tuple[list[dict], int]:
        """Poll contract events; callers persist a cursor and make handling idempotent."""
        web3, contract = self._ready()
        latest = web3.eth.block_number
        events: list[dict] = []
        block_times: dict[int, datetime] = {}
        names = [n for n in ("EvidenceRegistered", "EvidenceVerified", "EvidenceTampered", "CustodyTransferred")
                 if self._has_event(contract, n)]
        for name in names:
            for item in getattr(contract.events, name)().get_logs(from_block=from_block, to_block=latest):
                number = item["blockNumber"]
                if number not in block_times:
                    block_times[number] = _utc(web3.eth.get_block(number)["timestamp"])
                events.append({"name": name, "args": dict(item["args"]), "transactionHash": normalize_hex(item["transactionHash"]),
                               "blockNumber": number, "timestamp": block_times[number]})
        return sorted(events, key=lambda event: (event["blockNumber"], event["transactionHash"])), latest


blockchain_service = EvidenceBlockchainService()
