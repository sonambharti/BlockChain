# -*- coding: utf-8 -*-
"""
Created on Tue Sep 20 20:13:08 2022

@author: CS_LAB_26
"""

import datetime
import hashlib
import json
from flask import Flask, jsonify


# Build a Blockchain

class Blockchain:
    def __init__(self):
        self.chain = []
        self.create_block(proof=1, previous_Hash = '0')
        
    def create_block(self, proof,previous_Hash):
        block = {'index': len(self.chain)+1,
                 'proof' : proof,
                 'previous_Hash' : previous_Hash,
                 'timestamp' : str(datetime.datetime.now())
            }
        self.chain.append(block)
        return block
    
    def get_previous_block(self):
        return self.chain[-1]
    
    def proof_of_work(self, prev_proof):
        new_proof = 1
        check_proof = False
        
        while check_proof == False:
            hash_func = hashlib.sha256(str(new_proof**3 - prev_proof**3).encode()).hexdigest()
            if hash_func[:5] == '00000':
                check_proof = True
            else:
                new_proof += 1
        
        return new_proof
    
    def hash(self, block):
        encoded_block = json.dumps(block, sort_keys = True).encode()
        return hashlib.sha256(encoded_block).hexdigest()
    
    def is_chainValid(self, chain):
        previous_block = chain[0]
        block_indx = 1
        
        while block_indx < len(chain):
            block = chain[block_indx]
            if block['previous_Hash'] != self.hash(previous_block):
                return False
            prev_proof = previous_block['proof']
            proof = block['proof']
            hash_func = hashlib.sha256(str(proof**3 - prev_proof**3).encode()).hexdigest()
            if hash_func[:5] != '00000':
                return False
            previous_block = block
            block_indx += 1
            
            return True
        
        
# Mining our Blockchain

# Creating a Web App
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
# Creating a Blockchain
blockchain = Blockchain()



#Mining a new block
@app.route('/mine_block', methods = ['GET'])
def mine_block():
    previous_block = blockchain.get_previous_block()
    prev_proof = previous_block['proof']
    proof = blockchain.proof_of_work(prev_proof)
    prev_hash = blockchain.hash(previous_block)
    block = blockchain.create_block(proof, prev_hash)
    
    response = { 'message': "Congratulations!!! We are here to learn the blockchin...And You just mined a block successfully.:)",
                'index': block['index'],
                'proof': block['proof'],
                'previous_Hash' : block['previous_Hash'],
                'timestamp' : block['timestamp']
        }
    
    return jsonify(response), 200





#Getting chain
@app.route('/get_chain', methods = ['GET'])
def get_chain():
    response = {'chain': blockchain.chain,
                'length': len(blockchain.chain)
        }
    return jsonify(response), 200




@app.route('/is_valid', methods = ['GET'])
def is_valid():
    is_valid = blockchain.is_chainValid(blockchain.chain)
    if is_valid:
        response = {'message': "Congratulations!!! This chain is valid..."}
    else:
        response = {'message': "This chain is not valid..."}


# Running the app
app.run(host = '0.0.0.0', port = 5000)


