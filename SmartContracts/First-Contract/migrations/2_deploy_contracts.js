var Adoption = artifacts.require("D:/Blockchain/SmartContracts/First-Contract/contracts/Adoption.sol");

module.exports = function(deployer) {
  deployer.deploy(Adoption);
};