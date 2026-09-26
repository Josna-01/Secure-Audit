// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title EvidenceRegistry
 * @author Secure Audits System
 * @notice Production-grade smart contract for digital evidence integrity and chain-of-custody tracking.
 * @dev Stores immutable evidence metadata and custody logs on the blockchain without storing raw files.
 */
contract EvidenceRegistry {

    /**
     * @notice Struct representing immutable metadata of registered digital evidence.
     * @param evidenceId Unique identifier assigned to the evidence item.
     * @param caseId Associated criminal or forensic case identifier.
     * @param fileName Original file name of the digital evidence item.
     * @param sha256Hash Cryptographic SHA-256 digest of the evidence file payload.
     * @param uploadedBy Identifier of the investigating officer or system registering the file.
     * @param uploadTimestamp Unix timestamp (in seconds) when evidence was registered on-chain.
     * @param exists Boolean flag ensuring evidence existence and preventing duplication.
     */
    struct Evidence {
        string evidenceId;
        string caseId;
        string fileName;
        string sha256Hash;
        string uploadedBy;
        uint256 uploadTimestamp;
        bool exists;
    }

    /**
     * @notice Struct representing an individual entry in the chain-of-custody audit log.
     * @param officerId Identifier of the officer or custodian taking the action.
     * @param action Description of action performed ("REGISTERED", "VERIFIED", or "TRANSFERRED").
     * @param timestamp Unix timestamp (in seconds) when the custody event occurred.
     */
    struct CustodyRecord {
        string officerId;
        string action;
        uint256 timestamp;
    }

    /// @dev Mapping from evidence ID to Evidence metadata struct.
    mapping(string => Evidence) private _evidences;

    /// @dev Mapping from evidence ID to an ordered list of CustodyRecord structs.
    mapping(string => CustodyRecord[]) private _custodyHistory;

    /**
     * @notice Event emitted when new digital evidence is registered.
     * @param evidenceId Unique identifier for the evidence.
     * @param caseId Associated case identifier.
     * @param sha256Hash SHA-256 hash digest of the evidence file.
     * @param uploadedBy Officer or agent who uploaded the evidence.
     * @param timestamp Timestamp of registration.
     */
    event EvidenceRegistered(
        string indexed evidenceId,
        string caseId,
        string sha256Hash,
        string uploadedBy,
        uint256 timestamp
    );

    /**
     * @notice Event emitted when evidence hash verification is performed.
     * @param evidenceId Unique identifier for the evidence being verified.
     * @param sha256Hash Provided SHA-256 hash digest compared against stored metadata.
     * @param isMatch True if provided hash matches stored hash; false otherwise.
     * @param timestamp Timestamp of verification execution.
     */
    event EvidenceVerified(
        string indexed evidenceId,
        string sha256Hash,
        bool isMatch,
        uint256 timestamp
    );

    /**
     * @notice Event emitted when evidence custody is transferred or custody record appended.
     * @param evidenceId Unique identifier for the evidence.
     * @param officerId Officer associated with the custody action.
     * @param action Custody action code ("REGISTERED", "VERIFIED", or "TRANSFERRED").
     * @param timestamp Timestamp of custody record creation.
     */
    event CustodyTransferred(
        string indexed evidenceId,
        string officerId,
        string action,
        uint256 timestamp
    );

    /**
     * @notice Registers new digital evidence metadata and automatically creates the initial REGISTERED custody record.
     * @dev Enforces validation against duplicate IDs and empty string fields.
     * @param evidenceId Unique identifier string for the evidence.
     * @param caseId Case identifier string.
     * @param fileName Original file name of the evidence item.
     * @param sha256Hash SHA-256 digest string of the file.
     * @param uploadedBy ID or username of the officer registering the evidence.
     */
    function registerEvidence(
        string calldata evidenceId,
        string calldata caseId,
        string calldata fileName,
        string calldata sha256Hash,
        string calldata uploadedBy
    ) external {
        require(bytes(evidenceId).length > 0, "Evidence ID cannot be empty");
        require(bytes(caseId).length > 0, "Case ID cannot be empty");
        require(bytes(fileName).length > 0, "File name cannot be empty");
        require(bytes(sha256Hash).length > 0, "SHA256 hash cannot be empty");
        require(bytes(uploadedBy).length > 0, "Uploaded by officer ID cannot be empty");
        require(!_evidences[evidenceId].exists, "Evidence ID already registered");

        _evidences[evidenceId] = Evidence({
            evidenceId: evidenceId,
            caseId: caseId,
            fileName: fileName,
            sha256Hash: sha256Hash,
            uploadedBy: uploadedBy,
            uploadTimestamp: block.timestamp,
            exists: true
        });

        _custodyHistory[evidenceId].push(CustodyRecord({
            officerId: uploadedBy,
            action: "REGISTERED",
            timestamp: block.timestamp
        }));

        emit EvidenceRegistered(evidenceId, caseId, sha256Hash, uploadedBy, block.timestamp);
        emit CustodyTransferred(evidenceId, uploadedBy, "REGISTERED", block.timestamp);
    }

    /**
     * @notice Verifies the stored SHA-256 hash against a provided hash for integrity audit.
     * @param evidenceId Unique identifier for the registered evidence.
     * @param sha256Hash Provided SHA-256 hash to compare against on-chain metadata.
     * @return isMatch True if hashes match, false otherwise.
     */
    function verifyEvidence(
        string calldata evidenceId,
        string calldata sha256Hash
    ) external returns (bool isMatch) {
        require(_evidences[evidenceId].exists, "Evidence does not exist");
        require(bytes(sha256Hash).length > 0, "SHA256 hash cannot be empty");

        isMatch = (keccak256(bytes(_evidences[evidenceId].sha256Hash)) == keccak256(bytes(sha256Hash)));

        emit EvidenceVerified(evidenceId, sha256Hash, isMatch, block.timestamp);
        return isMatch;
    }

    /**
     * @notice Retrieves full metadata for a registered evidence item.
     * @param evidenceId Unique identifier of the target evidence.
     * @return Evidence struct containing full evidence metadata.
     */
    function getEvidence(
        string calldata evidenceId
    ) external view returns (Evidence memory) {
        require(_evidences[evidenceId].exists, "Evidence does not exist");
        return _evidences[evidenceId];
    }

    /**
     * @notice Appends a new custody entry to an evidence item's chain-of-custody history.
     * @dev Validates that the custody action is one of "REGISTERED", "VERIFIED", or "TRANSFERRED".
     * @param evidenceId Unique identifier of target evidence.
     * @param officerId ID of officer associated with the custody action.
     * @param action Custody action taken ("REGISTERED", "VERIFIED", "TRANSFERRED").
     */
    function addCustodyRecord(
        string calldata evidenceId,
        string calldata officerId,
        string calldata action
    ) external {
        require(_evidences[evidenceId].exists, "Evidence does not exist");
        require(bytes(officerId).length > 0, "Officer ID cannot be empty");
        require(bytes(action).length > 0, "Action cannot be empty");

        bytes32 actionHash = keccak256(bytes(action));
        require(
            actionHash == keccak256(bytes("REGISTERED")) ||
            actionHash == keccak256(bytes("VERIFIED")) ||
            actionHash == keccak256(bytes("TRANSFERRED")),
            "Invalid custody action"
        );

        _custodyHistory[evidenceId].push(CustodyRecord({
            officerId: officerId,
            action: action,
            timestamp: block.timestamp
        }));

        emit CustodyTransferred(evidenceId, officerId, action, block.timestamp);
    }

    /**
     * @notice Retrieves complete chain-of-custody audit trail for an evidence item.
     * @param evidenceId Unique identifier of target evidence.
     * @return Array of CustodyRecord structs representing the custody history.
     */
    function getCustodyHistory(
        string calldata evidenceId
    ) external view returns (CustodyRecord[] memory) {
        require(_evidences[evidenceId].exists, "Evidence does not exist");
        return _custodyHistory[evidenceId];
    }
}
