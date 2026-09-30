"""Throwaway Ganache node + EvidenceRegistry deployment for integration tests.

Never touches the development chain on 8545: the node runs in memory on a free port
and is killed when the test finishes.
"""
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "blockchain" / "artifacts" / "contracts" / "EvidenceRegistry.sol" / "EvidenceRegistry.json"


def ganache_available() -> bool:
    return shutil.which("ganache") is not None and ARTIFACT.is_file()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class GanacheNode:
    def __init__(self) -> None:
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.process = None

    def start(self) -> "GanacheNode":
        self.process = subprocess.Popen(
            [shutil.which("ganache"), "--server.host", "127.0.0.1", "--server.port", str(self.port),
             "--chain.chainId", "1337", "--wallet.deterministic", "--logging.quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if Web3(Web3.HTTPProvider(self.url)).is_connected():
                    return self
            except Exception:
                pass
            time.sleep(0.5)
        self.stop()
        raise RuntimeError("Ganache did not start")

    def stop(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        if os.name == "nt":
            # ganache is a .cmd shim on Windows; kill() would stop only the shim and
            # leave the node process running, so terminate the whole tree.
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            self.process.kill()
        self.process.wait(timeout=10)

    def deploy(self, deployment_file: Path) -> str:
        web3 = Web3(Web3.HTTPProvider(self.url))
        artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        factory = web3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
        tx = factory.constructor().transact({"from": web3.eth.accounts[0]})
        address = web3.eth.wait_for_transaction_receipt(tx).contractAddress
        deployment_file.write_text(json.dumps({"address": address, "chainId": 1337}), encoding="utf-8")
        return address
