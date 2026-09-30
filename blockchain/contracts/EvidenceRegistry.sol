// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title EvidenceRegistry
 * @author Secure Audits System
 * @notice Digital evidence integrity and chain-of-custody registry.
 * @dev Stores immutable evidence metadata and custody logs on-chain without storing raw files.
 *
 * Compatibility: every external function keeps the signature and return type of the
 * original contract, and the revert strings "Evidence does not exist" and
 * "Evidence ID already registered" are unchanged because the backend matches on them.
 *
 * Security model: only the owner and addresses the owner authorises ("registrars",
 * i.e. the backend's signing account) may write. Reads stay public so that any party
 * can independently check a registration.
 */
contract EvidenceRegistry {

    /// @dev Length of a lowercase hex SHA-256 digest.
    uint256 private constant SHA256_HEX_LENGTH = 64;
    /// @dev Upper bound for identifier strings (UUIDs are 36 characters).
    uint256 private constant MAX_ID_LENGTH = 128;
    /// @dev Upper bound for stored file names, to cap storage cost.
    uint256 private constant MAX_FILE_NAME_LENGTH = 255;

    /**
     * @notice Immutable metadata of a registered evidence item.
     * @param evidenceId Unique identifier assigned to the evidence item.
     * @param caseId Associated case identifier.
     * @param fileName Original file name of the evidence item.
     * @param sha256Hash Lowercase hex SHA-256 digest of the evidence file.
     * @param uploadedBy Identifier of the officer or system registering the file.
     * @param uploadTimestamp Unix timestamp (seconds) of on-chain registration.
     * @param exists Existence flag preventing duplicate registration.
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
     * @notice One entry in the chain-of-custody log.
     * @param officerId Identifier of the officer or custodian taking the action.
     * @param action "REGISTERED", "VERIFIED" or "TRANSFERRED".
     * @param timestamp Unix timestamp (seconds) of the custody event.
     */
    struct CustodyRecord {
        string officerId;
        string action;
        uint256 timestamp;
    }

    /// @notice Account that deployed the registry; may manage registrars.
    address public owner;

    /// @notice Accounts allowed to write evidence and custody records.
    mapping(address => bool) public isRegistrar;

    /// @notice Number of evidence items registered on this contract.
    uint256 public totalEvidence;

    mapping(string => Evidence) private _evidences;
    mapping(string => CustodyRecord[]) private _custodyHistory;

    event EvidenceRegistered(
        string indexed evidenceId,
        string caseId,
        string sha256Hash,
        string uploadedBy,
        uint256 timestamp
    );

    /// @notice Emitted for every verification; isMatch carries the verdict.
    event EvidenceVerified(
        string indexed evidenceId,
        string sha256Hash,
        bool isMatch,
        uint256 timestamp
    );

    /// @notice Emitted in addition to EvidenceVerified when the supplied hash does not match.
    event EvidenceTampered(
        string indexed evidenceId,
        string registeredHash,
        string suppliedHash,
        uint256 timestamp
    );

    event CustodyTransferred(
        string indexed evidenceId,
        string officerId,
        string action,
        uint256 timestamp
    );

    event RegistrarUpdated(address indexed account, bool authorised);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    modifier onlyOwner() {
        require(msg.sender == owner, "Caller is not the owner");
        _;
    }

    modifier onlyRegistrar() {
        require(isRegistrar[msg.sender], "Caller is not an authorised registrar");
        _;
    }

    modifier evidenceExists(string calldata evidenceId) {
        require(_evidences[evidenceId].exists, "Evidence does not exist");
        _;
    }

    constructor() {
        owner = msg.sender;
        isRegistrar[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit RegistrarUpdated(msg.sender, true);
    }

    // ------------------------------------------------------------------ administration

    /// @notice Authorise or revoke a writing account (for example a new backend key).
    function setRegistrar(address account, bool authorised) external onlyOwner {
        require(account != address(0), "Registrar cannot be the zero address");
        isRegistrar[account] = authorised;
        emit RegistrarUpdated(account, authorised);
    }

    /// @notice Hand ownership to another account (for key rotation).
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "New owner cannot be the zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    // ------------------------------------------------------------------ evidence

    /**
     * @notice Registers evidence metadata and creates the initial REGISTERED custody record.
     * @dev Rejects duplicate IDs, empty or oversized fields and malformed digests.
     */
    function registerEvidence(
        string calldata evidenceId,
        string calldata caseId,
        string calldata fileName,
        string calldata sha256Hash,
        string calldata uploadedBy
    ) external onlyRegistrar {
        _requireId(evidenceId, "Evidence ID cannot be empty", "Evidence ID is too long");
        _requireId(caseId, "Case ID cannot be empty", "Case ID is too long");
        _requireId(uploadedBy, "Uploaded by officer ID cannot be empty", "Officer ID is too long");
        require(bytes(fileName).length > 0, "File name cannot be empty");
        require(bytes(fileName).length <= MAX_FILE_NAME_LENGTH, "File name is too long");
        require(bytes(sha256Hash).length == SHA256_HEX_LENGTH, "SHA256 hash must be 64 hex characters");
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
        unchecked { totalEvidence += 1; }

        _custodyHistory[evidenceId].push(CustodyRecord({
            officerId: uploadedBy,
            action: "REGISTERED",
            timestamp: block.timestamp
        }));

        emit EvidenceRegistered(evidenceId, caseId, sha256Hash, uploadedBy, block.timestamp);
        emit CustodyTransferred(evidenceId, uploadedBy, "REGISTERED", block.timestamp);
    }

    /**
     * @notice Compares a supplied SHA-256 digest with the registered one and records the verdict.
     * @dev Restricted to registrars so that verdict events in the log come only from the backend,
     *      which computes the digest from the stored file itself.
     * @return isMatch True if the digests match.
     */
    function verifyEvidence(
        string calldata evidenceId,
        string calldata sha256Hash
    ) external onlyRegistrar evidenceExists(evidenceId) returns (bool isMatch) {
        require(bytes(sha256Hash).length == SHA256_HEX_LENGTH, "SHA256 hash must be 64 hex characters");

        string storage registered = _evidences[evidenceId].sha256Hash;
        isMatch = keccak256(bytes(registered)) == keccak256(bytes(sha256Hash));

        emit EvidenceVerified(evidenceId, sha256Hash, isMatch, block.timestamp);
        if (!isMatch) {
            emit EvidenceTampered(evidenceId, registered, sha256Hash, block.timestamp);
        }
        return isMatch;
    }

    /// @notice Read-only integrity check that records nothing (no gas when called off-chain).
    function checkEvidence(
        string calldata evidenceId,
        string calldata sha256Hash
    ) external view evidenceExists(evidenceId) returns (bool) {
        return keccak256(bytes(_evidences[evidenceId].sha256Hash)) == keccak256(bytes(sha256Hash));
    }

    /// @notice Full metadata for a registered evidence item.
    function getEvidence(
        string calldata evidenceId
    ) external view evidenceExists(evidenceId) returns (Evidence memory) {
        return _evidences[evidenceId];
    }

    /// @notice True when the ID has been registered (never reverts).
    function isRegistered(string calldata evidenceId) external view returns (bool) {
        return _evidences[evidenceId].exists;
    }

    // ------------------------------------------------------------------ custody

    /**
     * @notice Appends a custody entry ("REGISTERED", "VERIFIED" or "TRANSFERRED").
     */
    function addCustodyRecord(
        string calldata evidenceId,
        string calldata officerId,
        string calldata action
    ) external onlyRegistrar evidenceExists(evidenceId) {
        _requireId(officerId, "Officer ID cannot be empty", "Officer ID is too long");
        require(bytes(action).length > 0, "Action cannot be empty");

        bytes32 actionHash = keccak256(bytes(action));
        require(
            actionHash == keccak256("REGISTERED") ||
            actionHash == keccak256("VERIFIED") ||
            actionHash == keccak256("TRANSFERRED"),
            "Invalid custody action"
        );

        _custodyHistory[evidenceId].push(CustodyRecord({
            officerId: officerId,
            action: action,
            timestamp: block.timestamp
        }));

        emit CustodyTransferred(evidenceId, officerId, action, block.timestamp);
    }

    /// @notice Complete chain-of-custody history, oldest first.
    function getCustodyHistory(
        string calldata evidenceId
    ) external view evidenceExists(evidenceId) returns (CustodyRecord[] memory) {
        return _custodyHistory[evidenceId];
    }

    /// @notice Number of custody entries, so clients can page through long histories.
    function getCustodyCount(
        string calldata evidenceId
    ) external view evidenceExists(evidenceId) returns (uint256) {
        return _custodyHistory[evidenceId].length;
    }

    // ------------------------------------------------------------------ internal

    function _requireId(string calldata value, string memory emptyMessage, string memory longMessage) private pure {
        require(bytes(value).length > 0, emptyMessage);
        require(bytes(value).length <= MAX_ID_LENGTH, longMessage);
    }
}
