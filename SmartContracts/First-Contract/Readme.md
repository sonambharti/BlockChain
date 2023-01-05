These are the easy steps to follow your first contract using truffle..........
//I have also attached the output file for your refrence.

**Commands:**

1. mkdir First-Contract      //Optional
2. truffle unbox pet-shop
3. truffle compile          //To compile contract(.sol) file
4. truffle migrate         //to migrate the contract over network
5. truffle test            //to test the tst file




If there is any error during "truffle migrate", make sure you have open your "ganache" in background and written correct syntax for your code, 
also enter correct file location in the code. Then after....
Commands:
1. truffle compile --reset
2. truffle migrate --reset.




**Note:**
In the First-Contract directory "node_modules" directory is missing. So for that go to the current loction of "First-Contract" through cmd
and run command "npm install"
