                Command to execute this file ...

1.  docker run -itd -p 9701-9708:9701-9708 ghoshbishakh/indy_pool
2.  docker ps
3.  docker exec -it "container_id" bash


                Command to see the several log of Nodes in the pool

4.  indy@"container-id":/$ tail -f /var/log/indy/sandbox/Node1.log
5.  indy@"container-id":/$ tail -f /var/log/indy/sandbox/Node2.log
6.  indy@"container-id":/$ tail -f /var/log/indy/sandbox/Node3.log
7.  indy@"container-id":/$ tail -f /var/log/indy/sandbox/Node4.log


                Command to create pool.txn file Content

8.  cat /var/lib/indy/sandbox/pool_transactions_genesis
9.  Now copy the output from terminal and paste it to the file "file_name.txn" in your project.
10. Now run the code in terminal under required environment. Command to run the file "python3 file_name.py"