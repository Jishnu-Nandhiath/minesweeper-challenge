import asyncio
from websockets.asyncio.server import serve
import uuid, json
from constants import WEBHOOK_SIGNATURE_SECRET
from cryptography.fernet import Fernet
import redis

"""
player connection initialization:
    {"command": "register_player", "signature": "dfefdfdf"} -> uuid() on response
    
socket json, signature verification
A timer like within 10 seconds next response from either of the player didn't come. Then the other player loses.

And if I get a request like someone lost. Or someone won -> Then immediately I send a request to both the clients
to reset the game and forfeit. 


{"command": "}

1. register,   -> response "accept": True, "data"    player_id, signature
2. start,  -> response "accept": True, "data":  signature
3. game_over -> response: "accept": True, "data: -> player_id (winner), signature

the received player_id is expected on all the subsequent requests

redis structure

active player list = [uuid list]
player and opponent list -> player_id key -> opponent value

"""

# 3. time_out,  player_id ,signature


r = redis.Redis(host="localhost", port=6381)

async def socket_client(websocket):
    async for message in websocket:
        print(message)
        message_json = json.loads(message)
        print(message_json)
        # webhook_verification_status = verify_webhook_signature(
        #     message_body=message_json
        # )
        # if not webhook_verification_status:
        # #     error_message = {"accept": False, "message": "Invalid Request!"}

        #     await websocket.send(json.dumps(error_message))

        processed_message = process_messsage(message_json)
        await websocket.send(json.dumps(processed_message))

def process_messsage(message_json: json):
    print(message_json)
    request_command = message_json.get("command")
    message = None
    if request_command == "register":
        player_id = get_player_id()
        message = {"accept": True, "command": "register", "player_id": player_id}
        r.lpush("match_pool", player_id)  # add a player who is ready to play in the match pool

    elif request_command == "start":
        player_id = message_json.get("player_id")
        match_pool_players = r.lrange("match_pool", 0, -1)
        for player in match_pool_players:
            if player != player_id:
                r.set(player, player_id)   # setting key value pairs as opponents, This is inefficient with 2 keys. Need to iterate again on this
                r.set(player_id, player)
                message = {"accept": True, "command": "start", "player_id": player_id, "opponent_id": player}
        message = {"accept": False, "command": "start", "message": "please wait for some time!"}
    
    elif request_command == "game_over":
        player_id = message_json.get("player_id")
        message = {"accept": True, "command": "game_over", "winner": player_id}
        
    return json.dumps(message)


def get_player_id():
    return str(uuid.uuid4())


def verify_webhook_signature(message_body: str):
    signature = message_body["signature"]
    del message_body["signature"]
    if signature != generate_webhook_signature(message_body):
        return False
    return True


def generate_webhook_signature(message_body: json):
    fernet = Fernet(WEBHOOK_SIGNATURE_SECRET)
    message_string = json.dumps(message_body)
    message_string_bytes = str.encode(message_string)
    webhook_signature = fernet.encrypt(message_string_bytes)
    return webhook_signature.decode()


async def main():
    async with serve(socket_client, "localhost", 8765) as server:
        await server.serve_forever()


if __name__ == "__main__":
    print("started")
    asyncio.run(main())
