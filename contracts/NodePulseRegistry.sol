// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title NodePulseRegistry - on-chain health attestations for Portaldot nodes
/// @notice Off-chain monitors post compact health reports; anyone can read the latest status.
contract NodePulseRegistry {
    struct Report {
        uint64 blockHeight;   // best block seen by the node
        uint32 peers;         // connected peers
        uint16 score;         // 0-100 health score computed off-chain
        uint64 timestamp;     // block.timestamp of the report
        address reporter;
    }

    mapping(bytes32 => Report) public latest;      // nodeId => latest report
    mapping(bytes32 => address) public operatorOf; // nodeId => operator allowed to report
    bytes32[] public nodes;

    event NodeRegistered(bytes32 indexed nodeId, address indexed operator, string label);
    event PulseReported(bytes32 indexed nodeId, uint64 blockHeight, uint32 peers, uint16 score);

    function register(bytes32 nodeId, string calldata label) external {
        require(operatorOf[nodeId] == address(0), "taken");
        operatorOf[nodeId] = msg.sender;
        nodes.push(nodeId);
        emit NodeRegistered(nodeId, msg.sender, label);
    }

    function report(bytes32 nodeId, uint64 blockHeight, uint32 peers, uint16 score) external {
        require(operatorOf[nodeId] == msg.sender, "not operator");
        require(score <= 100, "score");
        latest[nodeId] = Report(blockHeight, peers, score, uint64(block.timestamp), msg.sender);
        emit PulseReported(nodeId, blockHeight, peers, score);
    }

    function nodeCount() external view returns (uint256) { return nodes.length; }
}
