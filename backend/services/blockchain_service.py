"""Resilient Web3 gateway. API routes never construct or submit blockchain calls."""
import json
import logging
import os
import socket
import subprocess
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from web3 import Web3
from web3.exceptions import ContractLogicError, TimeExhausted, Web3RPCError, Web3Exception

logger = logging.getLogger("secure_audit.blockchain")


class BlockchainUnavailable(RuntimeError):
    pass


class BlockchainTransactionError(RuntimeError):
    pass


class EvidenceBlockchainService:
    def __init__(self) -> None:
        self.rpc_url = os.getenv("ETHEREUM_RPC_URL", "http://127.0.0.1:8545")
        self.timeout = int(os.getenv("BLOCKCHAIN_TX_TIMEOUT_SECONDS", "90"))
        self.retries = int(os.getenv("BLOCKCHAIN_RETRIES", "3"))
        self.private_key = os.getenv("ETHEREUM_PRIVATE_KEY")
        self.sender = os.getenv("ETHEREUM_SENDER_ADDRESS")
        self._web3: Web3 | None = None
        self._contract = None
        self._runtime_address: str | None = None
        self._lock = threading.RLock()
        root = Path(__file__).resolve().parents[2]
        self._artifact_path = Path(os.getenv("EVIDENCE_REGISTRY_ARTIFACT", root / "blockchain" / "artifacts" / "contracts" / "EvidenceRegistry.sol" / "EvidenceRegistry.json"))
        self._deployment_path = Path(os.getenv("EVIDENCE_REGISTRY_DEPLOYMENT", root / "blockchain" / "deployments" / "localhost.json"))

    def is_rpc_alive(self, timeout: float = 1.5) -> bool:
        """Fast TCP liveness check to avoid long socket hangs when node is down."""
        try:
            parsed = urllib.parse.urlparse(self.rpc_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or 8545
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _redeploy_if_needed(self, web3: Web3, artifact: dict) -> str:
        """If contract is missing at configured address (e.g. after Ganache restart), redeploy automatically."""
        root = Path(__file__).resolve().parents[2]
        deploy_script = root / "blockchain" / "scripts" / "deploy.js"
        if deploy_script.is_file():
            logger.info("EvidenceRegistry not found on chain. Attempting auto-deployment via deploy.js...")
            try:
                res = subprocess.run(
                    ["node", "scripts/deploy.js"],
                    cwd=root / "blockchain",
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if res.returncode == 0 and self._deployment_path.is_file():
                    dep = json.loads(self._deployment_path.read_text(encoding="utf-8"))
                    self._runtime_address = dep["address"]
                    logger.info("Auto-deployment successful: %s", self._runtime_address)
                    return self._runtime_address
                else:
                    logger.error("Auto-deployment failed: %s %s", res.stdout, res.stderr)
            except Exception as e:
                logger.error("Auto-deployment script execution failed: %s", e)
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
            provider = Web3.HTTPProvider(self.rpc_url, request_kwargs={"timeout": 15})
            web3 = Web3(provider)
            if not web3.is_connected():
                raise BlockchainUnavailable(f"Ethereum provider is unavailable at {self.rpc_url}")
            if not self._artifact_path.is_file():
                raise BlockchainUnavailable("EvidenceRegistry ABI artifact is unavailable; run Hardhat compile first.")
            artifact = json.loads(self._artifact_path.read_text(encoding="utf-8"))

            address = None
            try:
                raw_addr = self._contract_address()
                address = Web3.to_checksum_address(raw_addr)
                has_code = bool(web3.eth.get_code(address))
            except Exception:
                has_code = False

            # Silently deploying a fresh, empty registry would orphan every
            # existing registration (all evidence would then fail verification),
            # so automatic redeployment is opt-in. Use the admin redeploy
            # endpoint deliberately instead.
            if not has_code and os.getenv("BLOCKCHAIN_AUTO_REDEPLOY", "false").strip().lower() in ("1", "true", "yes"):
                redeploy_addr = self._redeploy_if_needed(web3, artifact)
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
            logger.info("Connected to Ethereum chain=%s contract=%s", web3.eth.chain_id, address)

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
                "sender": self._sender(web3)
            }
        except BlockchainUnavailable as exc:
            return {"connected": False, "error": str(exc)}
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def _sender(self, web3: Web3) -> str:
        if self.private_key:
            return web3.eth.account.from_key(self.private_key).address
        if self.sender:
            return Web3.to_checksum_address(self.sender)
        accounts = web3.eth.accounts
        if not accounts:
            raise BlockchainUnavailable("No sender account configured. Set ETHEREUM_SENDER_ADDRESS or ETHEREUM_PRIVATE_KEY.")
        return accounts[0]

    def _transact(self, function) -> dict:
        last_error = None
        for attempt in range(self.retries):
            try:
                web3, contract = self._ready()
                sender = self._sender(web3)
                fn_name = getattr(function, 'fn_name', str(function))
                logger.info("[BLOCKCHAIN RPC] Preparing tx for function=%s sender=%s", fn_name, sender)
                tx = function.build_transaction({
                    "from": sender,
                    "nonce": web3.eth.get_transaction_count(sender, "pending"),
                    "chainId": web3.eth.chain_id
                })
                logger.info("[BLOCKCHAIN TX] Submitting transaction for %s...", fn_name)
                if self.private_key:
                    signed = web3.eth.account.sign_transaction(tx, self.private_key)
                    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
                else:
                    tx_hash = web3.eth.send_transaction(tx)
                
                tx_hash_hex = tx_hash.hex()
                logger.info("[BLOCKCHAIN TX HASH] %s submitted, awaiting receipt...", tx_hash_hex)
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=self.timeout, poll_latency=1)
                if receipt.status != 1:
                    logger.error("[BLOCKCHAIN TX REVERT] Transaction %s reverted", tx_hash_hex)
                    raise BlockchainTransactionError(f"Transaction reverted on chain: {tx_hash_hex}")
                
                block_info = web3.eth.get_block(receipt.blockNumber)
                block_timestamp = datetime.fromtimestamp(block_info["timestamp"], timezone.utc)
                logger.info("[BLOCKCHAIN RECEIPT] Confirmed in block=%s gas_used=%s", receipt.blockNumber, receipt.gasUsed)
                return {
                    "transactionHash": tx_hash_hex,
                    "blockNumber": receipt.blockNumber,
                    "gasUsed": receipt.gasUsed,
                    "contractAddress": receipt.to or (self._contract.address if self._contract else contract.address),
                    "timestamp": block_timestamp
                }
            except (ContractLogicError, Web3RPCError, Web3Exception, TimeExhausted, ValueError, OSError, BlockchainUnavailable) as exc:
                last_error = exc
                logger.warning("[BLOCKCHAIN ERROR] Transaction attempt %s/%s failed: %s", attempt + 1, self.retries, exc)
                self._web3 = self._contract = None
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise BlockchainTransactionError(f"Blockchain transaction failed after {self.retries} attempts: {last_error}")

    def register_evidence(self, evidence_id: str, case_id: str, file_name: str, sha256_hash: str, officer_id: str) -> dict:
        _, contract = self._ready()
        try:
            existing = contract.functions.getEvidence(evidence_id).call()
            if existing and existing[-1]:
                raise BlockchainTransactionError("Evidence is already registered on-chain")
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as e:
            if "does not exist" in str(e).lower():
                pass
            else:
                logger.debug("getEvidence probe note: %s", e)
        return self._transact(contract.functions.registerEvidence(evidence_id, case_id, file_name, sha256_hash, officer_id))

    def verify_evidence(self, evidence_id: str, sha256_hash: str, officer_id: str) -> tuple[bool, dict]:
        _, contract = self._ready()
        try:
            chain_evidence = contract.functions.getEvidence(evidence_id).call()
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as e:
            if "does not exist" in str(e).lower():
                raise BlockchainTransactionError(f"Evidence '{evidence_id}' is not registered on the blockchain")
            raise
        stored_hash = chain_evidence[3]
        verification = self._transact(contract.functions.verifyEvidence(evidence_id, sha256_hash))
        # The result is the contract's own verdict: the isMatch field of the
        # EvidenceVerified event emitted by this transaction.
        chain_is_match = self._verified_event_result(verification["transactionHash"])
        if chain_is_match is None:
            raise BlockchainTransactionError("Verification transaction emitted no EvidenceVerified event")
        if chain_is_match != (stored_hash == sha256_hash):
            raise BlockchainTransactionError("On-chain verification result disagrees with the registered hash")
        custody = self._transact(contract.functions.addCustodyRecord(evidence_id, officer_id, "VERIFIED"))
        verification["custodyTransaction"] = custody
        verification["onChainHash"] = stored_hash
        verification["chainIsMatch"] = chain_is_match
        return chain_is_match, verification

    def _verified_event_result(self, tx_hash: str) -> bool | None:
        web3, contract = self._ready()
        receipt = web3.eth.get_transaction_receipt(tx_hash if tx_hash.startswith("0x") else "0x" + tx_hash)
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
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as e:
            if "does not exist" in str(e).lower():
                return None
            raise
        return {"evidenceId": record[0], "caseId": record[1], "fileName": record[2], "sha256Hash": record[3],
                "uploadedBy": record[4], "timestamp": datetime.fromtimestamp(record[5], timezone.utc)}

    def find_registration_receipt(self, evidence_id: str) -> dict | None:
        """Receipt details of the transaction that registered ``evidence_id`` (read-only)."""
        web3, contract = self._ready()
        logs = contract.events.EvidenceRegistered().get_logs(from_block=0, argument_filters={"evidenceId": evidence_id})
        if not logs:
            return None
        log = logs[0]
        receipt = web3.eth.get_transaction_receipt(log["transactionHash"])
        block = web3.eth.get_block(log["blockNumber"])
        return {"transactionHash": log["transactionHash"].hex(), "blockNumber": log["blockNumber"],
                "gasUsed": receipt.gasUsed, "contractAddress": contract.address,
                "timestamp": datetime.fromtimestamp(block["timestamp"], timezone.utc)}

    def transfer_custody(self, evidence_id: str, officer_id: str) -> dict:
        _, contract = self._ready()
        return self._transact(contract.functions.addCustodyRecord(evidence_id, officer_id, "TRANSFERRED"))

    def custody_history(self, evidence_id: str) -> list[dict]:
        _, contract = self._ready()
        try:
            records = contract.functions.getCustodyHistory(evidence_id).call()
            return [
                {
                    "officerId": item[0],
                    "officer_id": item[0],
                    "action": item[1],
                    "timestamp": datetime.fromtimestamp(item[2], timezone.utc).isoformat()
                }
                for item in records
            ]
        except (ContractLogicError, Web3RPCError, Web3Exception, ValueError) as e:
            if "does not exist" in str(e).lower():
                return []
            raise

    def recent_blocks(self, limit: int = 8) -> list[dict]:
        web3, _ = self._ready()
        return [{"number": number, "timestamp": datetime.fromtimestamp(web3.eth.get_block(number)["timestamp"], timezone.utc).isoformat(), "transactions": len(web3.eth.get_block(number)["transactions"])} for number in range(web3.eth.block_number, max(-1, web3.eth.block_number - limit), -1)]

    def events_since(self, from_block: int) -> tuple[list[dict], int]:
        """Poll contract events; callers persist a cursor and make handling idempotent."""
        web3, contract = self._ready()
        latest = web3.eth.block_number
        events: list[dict] = []
        for name in ("EvidenceRegistered", "EvidenceVerified", "CustodyTransferred"):
            for item in getattr(contract.events, name)().get_logs(from_block=from_block, to_block=latest):
                events.append({"name": name, "args": dict(item["args"]), "transactionHash": item["transactionHash"].hex(), "blockNumber": item["blockNumber"], "timestamp": datetime.fromtimestamp(web3.eth.get_block(item["blockNumber"])["timestamp"], timezone.utc)})
        return sorted(events, key=lambda event: (event["blockNumber"], event["transactionHash"])), latest


blockchain_service = EvidenceBlockchainService()
