import asyncio
import json
import time
from os.path import dirname

from indy import pool, wallet, did, ledger, anoncreds, blob_storage
from indy.error import IndyError, ErrorCode


# create wallet for each role

async def create_wallet(identity):
    print("\"{}\" -> Create wallet".format(identity['name']))
    try:
        await wallet.create_wallet(identity['wallet_config'], identity['wallet_credentials'])
    except IndyError as ex:
        if ex.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
            pass
    identity['wallet'] = await wallet.open_wallet(identity['wallet_config'], identity['wallet_credentials'])



# using getting_verinym particular role (like, gov) can register through steward

async def getting_verinym(from_, to):
    await create_wallet(to)

    (to['did'], to['key']) = await did.create_and_store_my_did(to['wallet'], "{}")
    
    from_['info'] = {
        'did' : to['did'],
        'verkey' : to['key'],
        'role' : to['role'] or None
    }

    await send_nym(from_['pool'], from_['wallet'], from_['did'], from_['info']['did'], from_[ 'info']['verkey'], from_['info']['role'])


# send_nym is actual transaction that indy supports

async def send_nym(pool_handle, wallet_handle, _did, new_did, new_key, role):
    nym_request = await ledger.build_nym_request(_did, new_did, new_key, None, role)
    print(nym_request)
    await ledger.sign_and_submit_request(pool_handle, wallet_handle, _did, nym_request)




async def ensure_previous_request_applied(pool_handle, checker_request, checker):
    for _ in range(3):
        response = json.loads(await ledger.submit_request(pool_handle, checker_request))
        try:
            if checker(response):
                return json.dumps(response)
        except TypeError:
            print("Something Wrong Happened.... ",TypeError)
        time.sleep(5)




async def get_cred_def(pool_handle, _did, cred_def_id):
    get_cred_def_request = await ledger.build_get_cred_def_request(_did, cred_def_id)
    get_cred_def_response = \
        await ensure_previous_request_applied(pool_handle, get_cred_def_request,
                                              lambda response: response['result']['data'] is not None)
    
    return await ledger.parse_get_cred_def_response(get_cred_def_response)



async def get_credential_for_referent(search_handle, referent):
    credentials = json.loads(
        await anoncreds.prover_fetch_credentials_for_proof_req(search_handle, referent, 10)
    )

    return credentials[0]['cred_info']



async def prover_get_entities_from_ledger(pool_handle, _did, identifiers, actor, timestamp_from=None, timestamp_to=None):
    schemas = {}
    cred_defs = {}
    rev_states = {}

    for item in identifiers.values():
        print("\n\n\"{}\" -> Get Schema from Ledger".format(actor))
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>,",item['schema_id'])
        (received_schema_id, recieved_schema) = await get_schema(pool_handle, _did, item['schema_id'])
        schemas[received_schema_id] = json.loads(recieved_schema)

        print("\"{}\" -> Get Claim Defintion from Ledger".format(actor))
        (received_cred_def_id, recieved_cred_def) = await get_cred_def(pool_handle, _did, item['cred_def_id'])
        cred_defs[received_cred_def_id] = json.loads(recieved_cred_def)

        if 'rev_reg_id' in item and item['rev_reg_id'] is not None:
            #Create Revocations States
            print("\"{}\" -> Get Revocation Registry Definition from Ledger".format(actor))
            get_revoc_reg_def_request = await ledger.build_get_revoc_reg_def_request(_did, item['rev_reg_id'])
            
            get_revoc_reg_def_response = \
                await ensure_previous_request_applied(pool_handle, get_revoc_reg_def_request, 
                                                      lambda response : response['result']['data'] is not None)
            
            (rev_reg_id, revoc_reg_def_json) = await ledger.parse_get_revoc_reg_def_response(get_revoc_reg_def_response)

            print("\n\n\"{}\" -> Get Revocation Registry Delta from Ledger".format(actor))
            if not timestamp_to: timestamp_to = int(time.time())
            get_revoc_reg_delta_request = \
                await ledger.build_get_revoc_reg_delta_request(_did, item['rev_reg_id'], timestamp_from, timestamp_to)
            
            get_revoc_reg_delta_response = \
                await ensure_previous_request_applied(pool_handle, get_revoc_reg_delta_request,
                                                      lambda response: response['result']['data'] is not None)
            
            (rev_reg_id, revoc_reg_delta_json, t) = \
                await ledger.parse_get_revoc_reg_delta_response(get_revoc_reg_delta_response)
            
            tails_reader_config = json.dumps(
                {'base_dir': dirname(json.loads(revoc_reg_def_json)['value']['tailsLocation']),
                                             'uri_pattern': ''})
            
            blob_storage_reader_cfg_handle = await blob_storage.open_reader('default', tails_reader_config)

            print('%s - Create Revocaton State', actor)

            rev_state_json = \
                await anoncreds.create_revocation_state(blob_storage_reader_cfg_handle,
                                                        revoc_reg_def_json,
                                                        revoc_reg_delta_json, t,
                                                        item['cred_rev_id'])
            
            rev_states[rev_reg_id] = {t : json.loads(rev_state_json)}

    return json.dumps(schemas), json.dumps(cred_defs), json.dumps(rev_states)
            
async def get_schema(pool_handle, _did, schema_id):
    get_schema_request = await ledger.build_get_schema_request(_did, schema_id)
    get_schema_response = await ensure_previous_request_applied(
        pool_handle, get_schema_request, lambda response: response['result']['data'] is not None)
    
    return await ledger.parse_get_schema_response(get_schema_response)


async def verifier_get_entities_from_ledger(pool_handle, _did, identifiers, actor, timestamp=None):
    schemas = {}
    cred_defs = {}
    rev_reg_defs = {}
    rev_regs = {}

    for item in identifiers:
        print("\"{}\" -> Get Schema from Ledger".format(actor))
        (received_schema_id, received_schema) = await get_schema(pool_handle, _did, item['schema_id'])
        schemas[received_schema_id] = json.loads(received_schema)

        print("\"{}\" -> Get Claim definition from Ledger".format(actor))
        (received_cred_def_id, received_cred_def) = await get_cred_def(pool_handle, _did, item['cred_def_id'])
        cred_defs[received_cred_def_id] = json.loads(received_cred_def)

        if 'rev_reg_id' in item and item['rev_reg_id'] is not None:
            #Get Revoction Definitions and Revocation Registries
            print("\"{}\" -> Get Revocation Definition from Ledger".format(actor))
            get_revoc_reg_def_request = await ledger.build_get_revoc_reg_def_request(_did, item['rev_reg_id'])

            get_revoc_reg_def_response = \
                await ensure_previous_request_applied(pool_handle, get_revoc_reg_def_request, 
                                                      lambda response: response['result']['data'] is not None)
            
            (rev_reg_id, revoc_reg_def_json) = await ledger.parse_get_revoc_reg_def_response(get_revoc_reg_def_response)


            print("\"{}\" -> Get Revocation Registry from Ledger".format(actor))
            if not timestamp:
                timestamp = item['timestamp']
            
            
            get_revoc_reg_request = \
                await ledger.build_get_revoc_reg_request(_did, item['rev_reg_id'], timestamp)
            
            get_revoc_reg_response = \
                await ensure_previous_request_applied(pool_handle, get_revoc_reg_request,
                                                      lambda response: response['result']['data'] is not None)
            
            (rev_reg_id, rev_reg_json, timestamp2) = await ledger.parse_get_revoc_reg_response(get_revoc_reg_response)

            rev_regs[rev_reg_id] = {timestamp2: json.loads(rev_reg_json)}
            rev_reg_defs[rev_reg_id] = json.loads(revoc_reg_def_json)

    
    
    return json.dumps(schemas), json.dumps(cred_defs), json.dumps(rev_reg_defs), json.dumps(rev_regs)
            
            
            


async def run():
    print("Indy demo program")

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 1.....")

    pool_ = {
        "name" : "pool1"
    }

    print("OpenPool Ledger: {}".format(pool_['name']))
    pool_['genesis_txn_path'] = "pool1.txn"
    pool_['config'] = json.dumps({"genesis_txn" : str(pool_['genesis_txn_path'])})
    print(pool_)

    #connection to pool

    await pool.set_protocol_version(2)


    try:
        await pool.create_pool_ledger_config(pool_['name'], pool_['config'])
    except IndyError as ex:
        if ex.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
            pass
    pool_['handle'] = await pool.open_pool_ledger(pool_['name'], None)
    
    print("pool-handle - ",pool_['handle'])




    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 2 - Configuring Steward.....")
    steward = {
        'name' : "Sovrin Steward",
        'wallet_config' : json.dumps({'id' : 'sovrin_steward_wallet'}),
        'wallet_credentials' : json.dumps({'key' : 'steward_wallet_key'}),
        'pool' : pool_['handle'],
        'seed' : '000000000000000000000000Steward1'
    }

    print(steward)

    await create_wallet(steward)
    print(steward["wallet"])
    steward["did_info"] = json.dumps({'seed' : steward['seed']})
    print(steward["did_info"])

    #did:demoindynetwork: Th7MpTaRZVRYnPiabds81Y
    steward['did'], steward['key'] = await did.create_and_store_my_did(steward['wallet'], steward['did_info'])




    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 3 - register DID for government.....")

    print("\n\n\n==============================")
    print("== Government registring Verinym ==")
    print("------------------------------------")

    government = {
        'name' : 'Government',
        'wallet_config' : json.dumps({'id' : 'government_wallet'}),
        'wallet_credentials' : json.dumps({'key' : 'government_wallet_key'}),
        'pool' : pool_['handle'],
        'role' : 'TRUST_ANCHOR'
    }

    await getting_verinym(steward, government)




    print("STEP 3 - register DID for University and Company.....")

    print("=====================================")
    print("== theUniversity getting Verinym ==")
    print("--------------------------------------")

    theUniversity = {
        'name' : 'theUniversity',
        'wallet_config' : json.dumps({'id' : 'theUniversity_wallet'}),
        'wallet_credentials' : json.dumps({'key' : 'theUniversity_wallet_key'}),
        'pool' : pool_['handle'],
        'role' : 'TRUST_ANCHOR'
    } 

    await getting_verinym(steward, theUniversity)


    print("=====================================")
    print("== theCompany getting Verinym ==")
    print("--------------------------------------")

    theCompany = {
        'name' : 'theCompany',
        'wallet_config' : json.dumps({'id' : 'theCompany_wallet'}),
        'wallet_credentials' : json.dumps({'key' : 'theCompany_wallet_key'}),
        'pool' : pool_['handle'],
        'role' : 'TRUST_ANCHOR'
    }
    
    await getting_verinym(steward, theCompany)





    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 4 - Government Create credential schema for Transcripts")
    print("=======================================")

    # ----------------------------------------------------
    # Government creates transcript schema

    print("\"Government\" -> Create \"Transcript\" Schema")
    transcript = {
        'name' : 'Transcript',
        'version' : '1.2',
        'attributes' : ['first_name', 'last_name', 'degree', 'status', 'year', 'average', 'ssn']
    }

    (government['transcript_schema_id' ], government['transcript_schema']) = \
        await anoncreds.issuer_create_schema(government['did'], transcript['name'], transcript['version'],
                                             json.dumps(transcript['attributes']))
    
    print(government['transcript_schema'])
    transcript_schema_id = government['transcript_schema_id']

    print("\"Government\" -> Send \"Transcript\" Schema to Ledger")

    #Sign and submit the schema to Indy ledger

    schema_request = await ledger.build_schema_request(government['did'], government['transcript_schema'])
    await ledger.sign_and_submit_request(government['pool'], government['wallet'], government['did'], schema_request)




    print("\n\n >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 5 - University creates Transcript Credential Definition")

    print("\n\n=============================================")
    print("=== theUniversity Credential Definition Setup ==")
    print("-----------------------------------------------------")

    print("\"theUniversity\" -> Get \"Transcript\" Schema from Ledger")
    

    #GET SCHEMA FROM LEDGER

    get_schema_request = await ledger.build_get_schema_request(theUniversity['did'], transcript_schema_id)
    get_schema_response = await ensure_previous_request_applied(theUniversity['pool'], get_schema_request, lambda response: response['result']['data'] is not None)
    (theUniversity['transcript_schema_id'], theUniversity['transcript_schema']) = await ledger.parse_get_schema_response(get_schema_response)



    # CREATE TRANSCRIPT CREDENTIAL DEFINITION

    print("\"theUniversity \" -> Create and store in Wallet \"theUniversity Transcript\" Credential Definition")

    #Here, revocation is set to false
    
    transcript_cred_def = {
        'tag': 'TAG1',
        'type': 'CL',
        'config': {"support_revocation" : False} 
    }

    (theUniversity['transcript_cred_def_id'], theUniversity['transcript_cred_def']) = \
        await anoncreds.issuer_create_and_store_credential_def(theUniversity['wallet'], 
                                                               theUniversity['did'], theUniversity['transcript_schema'], 
                                                               transcript_cred_def['tag'], transcript_cred_def['type'], 
                                                               json.dumps(transcript_cred_def['config']))
    
    print("\"theUniversity\" -> Send \"theUniversity Transcript\" Credential Definition to Ledger")

    
    # COMMIT CREDENTIAL DEFINITION TO LEDGER
    cred_def_request = await ledger.build_cred_def_request(theUniversity['did'], theUniversity['transcript_cred_def'])
    print("####credential defination", cred_def_request)
    await ledger.sign_and_submit_request(theUniversity['pool'], theUniversity['wallet'], theUniversity['did'], cred_def_request)

    print("\n\n >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> \n\nUniversity transcript cred def id\n", theUniversity['transcript_cred_def_id'])
    print("\n\n >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> \n\nUniversity transcript cred def\n", theUniversity['transcript_cred_def'])




    print("\n\n\nSTEP 6 - University Issues Transcript Credential to Alice")

    print("=========================================================")
    print("=== Getting Transcript with theUniversity ===")
    print("==========================================================")

    print("Setting up Alice Wallet")
    
    alice = {
        'name': 'Alice',
        'wallet_config': json.dumps({'id': 'alice_wallet'}),
        'wallet_credentials': json.dumps({'key': 'alice_wallet_key'}),
        'pool': pool_['handle'],
    }

    await create_wallet(alice)
    (alice['did'], alice['key']) = await did.create_and_store_my_did(alice['wallet'], "{}") #create and store did into user's wallet

    print("University creates and sends transcript credential offer to Alice.....")

    theUniversity['transcript_cred_offer'] = \
        await anoncreds.issuer_create_credential_offer(theUniversity['wallet'], 
                                                       theUniversity['transcript_cred_def_id'])


    #Over the network Offer will be sent to Alice
    print("\"theUniversity\" -> Send \"Transcript\" Credential Offer to Alice")
    alice['transcript_cred_offer'] = theUniversity['transcript_cred_offer']
    #print(alice['transcript_cred_offer'])


    print("Alice prepares transcript credential request.....")
    transcript_cred_offer_object = json.loads(alice['transcript_cred_offer']) #de-serializing transcript credential offer in JSON format

    #extract schema_id & credential definition id from the transcript cred offer

    alice['transcript_schema_id'] = transcript_cred_offer_object['schema_id']
    alice['transcript_cred_def_id'] = transcript_cred_offer_object['cred_def_id']

    print("\"Alice\" -> Create and store \"Alice\" Master Secret in Wallet")
    #master secret will ensure that issuer will issue only 1 & unique credential to one user such that w/o this master secret no one can present this did
    alice['master_secret_id'] = await anoncreds.prover_create_master_secret(alice['wallet'], None) 

    print("\"Alice\" -> Get \"theUniversity Transcript\" Credential Definition from Ledger")
    (alice['theUniversity_transcript_cred_def_id'], alice['theUniversity_transcript_cred_def']) = \
        await get_cred_def(alice['pool'], alice['did'], alice['transcript_cred_def_id'])
    

    print("\"Alice\" -> Create \"Transcript\" Credential Request for theUniversity")
    (alice['transcript_cred_request'], alice['transcript_cred_request_metadata']) = \
        await anoncreds.prover_create_credential_req(alice['wallet'], alice['did'],
                                                     alice['transcript_cred_offer'],
                                                     alice['theUniversity_transcript_cred_def'],
                                                     alice['master_secret_id'])

    
    print("\"Alice\" -> Send \"Transcript\" Credential Request to theUniversity")


    #Over the network alice request is sent to theUniversity
    theUniversity['transcript_cred_request'] = alice['transcript_cred_request']

    print("\n\nUniversity issues credential to Alice...")

    print("\"theUniversity\" -> Create \"Transcript\" Credential for Alice" )
    theUniversity['alice_transcript_cred_values'] = json.dumps({
        "first_name" : {"raw": "Alice", "encoded": "1139481716457488690172217916278103335" },
        "last_name": {"raw": "Garcia", "encoded": "5321642780241790123587902456789123452" },
        "degree": {"raw": "Bachelor of Science, Marketing" , "encoded": "12434523576212321" },
        "status": {"raw": "graduated", "encoded": "2213454313412354" },
        "ssn": {"raw": "123-45-6789" , "encoded": "3124141231422543541" },
        "year": {"raw": "2015", "encoded": "2015"},
        "average": {"raw": "5", "encoded": "5"}
        })

    theUniversity['transcript_cred'], _, _ = \
        await anoncreds.issuer_create_credential(theUniversity['wallet'], theUniversity['transcript_cred_offer'],
                                                 theUniversity['transcript_cred_request'],
                                                 theUniversity['alice_transcript_cred_values'], None, None)
    

    print(theUniversity['transcript_cred'])    

    #Over the network

    print("\"theUniversity\" -> Send \"Transcript\" Credential to Alice" )
    alice['transcript_cred'] = theUniversity['transcript_cred']


    print("\"Alice\" -> Store \"Transcript\" Credential from theUniversity" )
    _, alice['transcript_cred_def'] = await get_cred_def(alice['pool'], alice['did'], 
                                                          alice['transcript_cred_def_id'])
    

    await anoncreds.prover_store_credential(alice['wallet'], None, alice['transcript_cred_request_metadata'],
                                            alice['transcript_cred'], alice['transcript_cred_def'], None)
    
    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\nAlice transcript cred def\n", alice['transcript_cred_def'])
    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\nAlice transcript cred def id\n",alice['transcript_cred_def_id'])
    


    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> STEP 7 - Alice makes verifiable presentation to company..... ")

    #Creating application request (presentation request) --- validator - theCompany

    print("\"theCompany\" -> Create \"Job-Application\" Proof Request")
    nonce = await anoncreds.generate_nonce()

    theCompany['job_application_proof_request'] = json.dumps({
        'nonce': nonce,
        'name': 'Job-Application',
        'version': '0.1',
        'requested_attributes': {
            'attr1_referent': {
                'name': 'first_name'
            },
            'attr2_referent': {
                'name': 'last_name'
            },
            'attr3_referent': {
                'name': 'degree',
                'restrictions': [{'cred_def_id': theUniversity['transcript_cred_def_id']}]
            },
            'attr4_referent': {
                'name': 'status',
                'restrictions': [{'cred_def_id': theUniversity['transcript_cred_def_id']}]
            },
            'attr5_referent': {
                'name': 'ssn',
                'restrictions': [{'cred_def_id': theUniversity['transcript_cred_def_id']}]
            },
            'attr6_referent': {
                'name': 'phone_number'
            }
        },

        #predicate value is presented and verified as zero-knowledge proof
        'requested_predicates': {
            'predicate1_referent': {
                'name': 'average',
                'p_type': '>=',
                'p_value': 4,
                'restrictions': [{'cred_def_id': theUniversity['transcript_cred_def_id']}]
            }
        }
    })


    print("\n\n\"theCompany\" -> Send \"Job-Application\" Proof Request to Alice")

    #Over Network
    alice['job_application_proof_request'] = theCompany['job_application_proof_request']


    #Alice prepares the presentation
    print("\"Alice\" -> Get credentials for \"Job-Application\" Proof Request")


    #to search for job application proof req this prover_search_credentials_for_proof_req API is being used................
    search_for_job_application_proof_request = \
        await anoncreds.prover_search_credentials_for_proof_req(alice['wallet'],
                                                                alice['job_application_proof_request'], None)
    

    print("----------------------------------------------------")
    print("Job_App_Proof_Req: \n",search_for_job_application_proof_request)
    print("-------------------------------------------------------")

    cred_for_attr1 = await get_credential_for_referent(search_for_job_application_proof_request, 'attr1_referent')
    cred_for_attr2 = await get_credential_for_referent(search_for_job_application_proof_request, 'attr2_referent')
    cred_for_attr3 = await get_credential_for_referent(search_for_job_application_proof_request, 'attr3_referent')
    cred_for_attr4 = await get_credential_for_referent(search_for_job_application_proof_request, 'attr4_referent')
    cred_for_attr5 = await get_credential_for_referent(search_for_job_application_proof_request, 'attr5_referent')

    cred_for_predicate1 = \
        await get_credential_for_referent(search_for_job_application_proof_request, 'predicate1_referent')
    print("\n\ncredential attr1: ", cred_for_attr1)
    print("\n\npredicate credential: ", cred_for_predicate1)

    #print("ALL.......")
    #1st close all the search for proof-req before forming the alice /users job application proof
    
    await anoncreds.prover_close_credentials_search_for_proof_req(search_for_job_application_proof_request)

    #map diff credentials to diff attributes and predicates as well
    alice['creds_for_job_application_proof'] = {cred_for_attr1['referent']: cred_for_attr1,
                                                cred_for_attr2['referent']: cred_for_attr2,
                                                cred_for_attr3['referent']: cred_for_attr3,
                                                cred_for_attr4['referent']: cred_for_attr4,
                                                cred_for_attr5['referent']: cred_for_attr5,
                                                cred_for_predicate1['referent']: cred_for_predicate1}


    print("\n\nAlice credential for Job Application:\n",alice['creds_for_job_application_proof'])

    #get the schemas which are associated/required for job_applicaton
    alice['schemas_for_job_application'], alice['creds_defs_for_job_application'], \
        alice['revoc_states_for_job_application'] = \
            await prover_get_entities_from_ledger(alice['pool'], alice['did'],
                                                  alice['creds_for_job_application_proof'],
                                                  alice['name']) #fetch the trancript credential schema


    print("\n\n\"Alice\" -> Create \"Job-Application\" Proof")
    alice['job_application_requested_creds'] = json.dumps({
        'self_attested_attributes': {
        'attr1_referent': 'Alice',
        'attr2_referent': 'Garcia',
        'attr6_referent': '123-45-6789'
    },
    'requested_attributes': {
        'attr3_referent': {'cred_id': cred_for_attr3['referent'], 'revealed': True},
        'attr4_referent': {'cred_id': cred_for_attr4['referent'], 'revealed': True},
        'attr5_referent': {'cred_id': cred_for_attr5['referent'], 'revealed': True},
    },
    'requested_predicates': {'predicate1_referent': {'cred_id': cred_for_predicate1['referent']}}
    })

    
    #Presentation
    alice['job_application_proof'] = \
        await anoncreds.prover_create_proof(alice['wallet'], alice['job_application_proof_request'],
                                            alice['job_application_requested_creds'],
                                            alice['master_secret_id'], alice['schemas_for_job_application'],
                                            alice['creds_defs_for_job_application'],
                                            alice['revoc_states_for_job_application'])
    
    print("\n\nAlice job application proof:\n",alice['job_application_proof'])

    print("\n\n\"Alice\" -> Send \"Job-Application\" Proof to theCompany")

    #Over Network
    theCompany['job_application_proof'] = alice['job_application_proof']

    print("\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>STEP 8 - Company validates Alice's claims........................")

    job_application_proof_object = json.loads(theCompany['job_application_proof'])

    print("\n\nJob Application Proof Object : \n", job_application_proof_object)

    theCompany['schemas_for_job_application'], theCompany['cred_defs_for_job_application'], \
        theCompany['revoc_ref_defs_for_job_application'], theCompany['revoc_regs_for_job_application'] = \
            await verifier_get_entities_from_ledger(theCompany['pool'], theCompany['did'],
                                                    job_application_proof_object['identifiers'], theCompany['name'])
    

    print("\"theCompany\" -> Verify \"Job-Application\" Proof from Alice")

    assert 'Bachelor of Science, Marketing' == \
        job_application_proof_object['requested_proof']['revealed_attrs']['attr3_referent']['raw']
    
    assert 'graduated' == \
        job_application_proof_object['requested_proof']['revealed_attrs']['attr4_referent']['raw']
    
    assert '123-45-6789' == \
        job_application_proof_object['requested_proof']['revealed_attrs']['attr5_referent']['raw']
    
    assert 'Alice' == job_application_proof_object['requested_proof']['self_attested_attrs']['attr1_referent']
    assert 'Garcia' == job_application_proof_object['requested_proof']['self_attested_attrs']['attr2_referent']
    assert '123-45-6789' == job_application_proof_object['requested_proof']['self_attested_attrs']['attr6_referent']

    assert await anoncreds.verifier_verify_proof(theCompany['job_application_proof_request'], theCompany['job_application_proof'],
                                                 theCompany['schemas_for_job_application'],
                                                 theCompany['cred_defs_for_job_application'],
                                                 theCompany['revoc_ref_defs_for_job_application'],
                                                 theCompany['revoc_regs_for_job_application'])

    
loop = asyncio.get_event_loop()
loop.run_until_complete(run())