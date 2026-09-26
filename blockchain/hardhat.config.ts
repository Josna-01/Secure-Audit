import { defineConfig } from "hardhat/config";

export default defineConfig({
  solidity: {
    version: "0.8.28",
    settings: {
      evmVersion: "shanghai",
    },
  },
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
    },
  },
});
