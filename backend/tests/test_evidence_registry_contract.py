"""EvidenceRegistry contract tests against a throwaway in-memory Ganache node.

Requires the `ganache` CLI on PATH and a compiled artifact (npx hardhat compile in blockchain/);
skipped otherwise. Run from the backend directory:
    python -m unittest tests.test_evidence_registry_contract
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3  # noqa: E402
from web3.exceptions import ContractLogicError, Web3RPCError  # noqa: E402
from web3.logs import DISCARD  # noqa: E402

from tests.blockchain_harness import ARTIFACT, GanacheNode, ganache_available  # noqa: E402

HASH_A = "a" * 64
HASH_B = "b" * 64


@unittest.skipUnless(ganache_available(), "ganache CLI or compiled artifact not available")
class EvidenceRegistryContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = GanacheNode().start()
        cls.tmp = tempfile.TemporaryDirectory()
        address = cls.node.deploy(Path(cls.tmp.name) / "deployment.json")
        cls.web3 = Web3(Web3.HTTPProvider(cls.node.url))
        abi = json.loads(ARTIFACT.read_text(encoding="utf-8"))["abi"]
        cls.contract = cls.web3.eth.contract(address=address, abi=abi)
        cls.owner, cls.outsider, cls.second = cls.web3.eth.accounts[:3]

    @classmethod
    def tearDownClass(cls):
        cls.node.stop()
        cls.tmp.cleanup()

    def send(self, fn, sender=None):
        tx = fn.transact({"from": sender or self.owner})
        return self.web3.eth.wait_for_transaction_receipt(tx)

    def assertReverts(self, fn, message, sender=None):
        with self.assertRaises((ContractLogicError, Web3RPCError, ValueError)) as ctx:
            fn.transact({"from": sender or self.owner})
        self.assertIn(message.lower(), str(ctx.exception).lower())

    def register(self, evidence_id, sha=HASH_A):
        return self.send(self.contract.functions.registerEvidence(evidence_id, "case-1", "file.jpg", sha, "officer-1"))

    def test_register_and_read(self):
        self.register("ev-read")
        record = self.contract.functions.getEvidence("ev-read").call()
        self.assertEqual(record[3], HASH_A)
        self.assertTrue(self.contract.functions.isRegistered("ev-read").call())
        self.assertFalse(self.contract.functions.isRegistered("ev-none").call())
        self.assertEqual(self.contract.functions.getCustodyCount("ev-read").call(), 1)

    def test_duplicate_registration_rejected(self):
        self.register("ev-dup")
        self.assertReverts(self.contract.functions.registerEvidence("ev-dup", "c", "f", HASH_A, "o"),
                           "Evidence ID already registered")

    def test_input_validation(self):
        fn = self.contract.functions.registerEvidence
        self.assertReverts(fn("", "c", "f", HASH_A, "o"), "Evidence ID cannot be empty")
        self.assertReverts(fn("ev-bad", "c", "f", "abc", "o"), "SHA256 hash must be 64 hex characters")
        self.assertReverts(fn("ev-bad", "c", "x" * 256, HASH_A, "o"), "File name is too long")
        self.assertReverts(fn("x" * 129, "c", "f", HASH_A, "o"), "Evidence ID is too long")

    def test_only_registrars_can_write(self):
        self.register("ev-acl")
        self.assertReverts(self.contract.functions.registerEvidence("ev-acl2", "c", "f", HASH_A, "o"),
                           "not an authorised registrar", sender=self.outsider)
        self.assertReverts(self.contract.functions.verifyEvidence("ev-acl", HASH_B), "not an authorised registrar",
                           sender=self.outsider)
        self.assertReverts(self.contract.functions.addCustodyRecord("ev-acl", "o", "TRANSFERRED"),
                           "not an authorised registrar", sender=self.outsider)
        self.assertReverts(self.contract.functions.setRegistrar(self.outsider, True), "not the owner", sender=self.outsider)

    def test_owner_can_authorise_registrar(self):
        self.send(self.contract.functions.setRegistrar(self.second, True))
        self.send(self.contract.functions.registerEvidence("ev-second", "c", "f", HASH_A, "o"), sender=self.second)
        self.send(self.contract.functions.setRegistrar(self.second, False))
        self.assertReverts(self.contract.functions.registerEvidence("ev-second2", "c", "f", HASH_A, "o"),
                           "not an authorised registrar", sender=self.second)

    def test_verification_events(self):
        self.register("ev-verify")
        ok = self.send(self.contract.functions.verifyEvidence("ev-verify", HASH_A))
        verified = self.contract.events.EvidenceVerified().process_receipt(ok, errors=DISCARD)
        self.assertTrue(verified[0]["args"]["isMatch"])
        self.assertEqual(self.contract.events.EvidenceTampered().process_receipt(ok, errors=DISCARD), ())

        bad = self.send(self.contract.functions.verifyEvidence("ev-verify", HASH_B))
        self.assertFalse(self.contract.events.EvidenceVerified().process_receipt(bad, errors=DISCARD)[0]["args"]["isMatch"])
        tampered = self.contract.events.EvidenceTampered().process_receipt(bad, errors=DISCARD)
        self.assertEqual(tampered[0]["args"]["registeredHash"], HASH_A)
        self.assertEqual(tampered[0]["args"]["suppliedHash"], HASH_B)

    def test_read_only_check_and_unknown_evidence(self):
        self.register("ev-check")
        self.assertTrue(self.contract.functions.checkEvidence("ev-check", HASH_A).call())
        self.assertFalse(self.contract.functions.checkEvidence("ev-check", HASH_B).call())
        with self.assertRaises((ContractLogicError, Web3RPCError, ValueError)) as ctx:
            self.contract.functions.getEvidence("ev-unknown").call()
        self.assertIn("evidence does not exist", str(ctx.exception).lower())

    def test_custody_actions(self):
        self.register("ev-custody")
        self.send(self.contract.functions.addCustodyRecord("ev-custody", "officer-2", "TRANSFERRED"))
        self.assertReverts(self.contract.functions.addCustodyRecord("ev-custody", "officer-2", "DELETED"),
                           "Invalid custody action")
        history = self.contract.functions.getCustodyHistory("ev-custody").call()
        self.assertEqual([item[1] for item in history], ["REGISTERED", "TRANSFERRED"])


if __name__ == "__main__":
    unittest.main()
