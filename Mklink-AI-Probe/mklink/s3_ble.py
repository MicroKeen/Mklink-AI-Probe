"""Authenticated BLE configuration transport. Does not pair/remove OS devices.
Same framing/crypto implementation is packaged for the desktop companion.
"""
import asyncio
import hashlib
import hmac
import json
import secrets
import struct
import uuid
from bleak import BleakClient, BleakScanner
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SERVICE='9af50001-4c63-4c4d-8b4b-e4790a544401'
RX='9af50002-4c63-4c4d-8b4b-e4790a544401'
TX='9af50003-4c63-4c4d-8b4b-e4790a544401'
INFO='9af50004-4c63-4c4d-8b4b-e4790a544401'


class BleEndpoint:
    def __init__(self,address,token):
        self.address=address;self.token=token;self.client=None;self.sequence=0;self.message_id=0
        self.waiter=None;self.response=bytearray();self.response_total=0
    @staticmethod
    async def discover(timeout=8):
        found=await BleakScanner.discover(timeout=timeout,return_adv=True,service_uuids=[SERVICE])
        return [{'address':d.address,'name':a.local_name or d.name or 'Mklink Remote','rssi':a.rssi} for d,a in found.values() if SERVICE in [s.lower() for s in a.service_uuids]]
    async def __aenter__(self):
        self.client=BleakClient(self.address,timeout=15);await self.client.connect()
        info=await self.client.read_gatt_char(INFO)
        if len(info)!=17 or info[0]!=1:raise RuntimeError('Unsupported BLE configuration protocol')
        self.session_info=bytes(info)
        self.key=hmac.new(bytes.fromhex(self.token),b'MKLINK-BLE-v1'+bytes(info[1:]),hashlib.sha256).digest()[:16]
        await self.client.start_notify(TX,self._notify);return self
    async def __aexit__(self,*args):
        if self.client and self.client.is_connected:await self.client.disconnect()
        self.key=b'\0'*16
    def _notify(self,_char,packet):
        if len(packet)<7:return
        ident,offset,total=struct.unpack('<HHH',packet[:6])
        if ident!=self.message_id or not self.waiter or self.waiter.done():return
        if offset==0:self.response=bytearray();self.response_total=total
        if offset!=len(self.response) or total!=self.response_total or total>65535:
            self.waiter.set_exception(RuntimeError('BLE response fragment mismatch'));return
        self.response.extend(packet[6:])
        if len(self.response)==total:self.waiter.set_result(bytes(self.response))
    async def rpc(self,method,params=None,timeout=30):
        if self.waiter and not self.waiter.done():raise RuntimeError('Only one BLE request may be in flight')
        self.sequence+=1;self.message_id=(self.message_id+1)&65535
        seq=struct.pack('<I',self.sequence);nonce=secrets.token_bytes(12)
        request=dict(v=1,id=uuid.uuid4().hex,method=method,params=params or {})
        plain=json.dumps(request,ensure_ascii=False,separators=(',',':')).encode()
        packet=seq+nonce+AESGCM(self.key).encrypt(nonce,plain,b'mklink-ble-request-v1'+seq)
        self.last_packet=packet
        if len(packet)>4608:raise ValueError('BLE request exceeds negotiated application limit')
        self.waiter=asyncio.get_running_loop().create_future()
        chunk=min(238,max(14,self.client.mtu_size-9))
        for offset in range(0,len(packet),chunk):
            await self.client.write_gatt_char(RX,struct.pack('<HHH',self.message_id,offset,len(packet))+packet[offset:offset+chunk],response=True)
        # Match the production Rust transport: some Windows adapters retain the
        # final notification until another GATT operation. A metadata read does
        # not resend the mutation and must prove the authenticated session stable.
        try:
            result=await asyncio.wait_for(asyncio.shield(self.waiter),min(.25,timeout))
        except asyncio.TimeoutError:
            info=await self.client.read_gatt_char(INFO)
            if bytes(info)!=self.session_info:raise RuntimeError('BLE session changed; outcome unknown, no replay')
            result=await asyncio.wait_for(self.waiter,max(.01,timeout-.25))
        if len(result)<33 or result[:4]!=seq:raise RuntimeError('BLE response sequence mismatch')
        plain=AESGCM(self.key).decrypt(result[4:16],result[16:],b'mklink-ble-response-v1'+seq)
        reply=json.loads(plain)
        if reply.get('v')!=1 or reply.get('id')!=request['id']:raise RuntimeError('BLE response identity mismatch')
        if not reply.get('ok'):raise RpcError(reply.get('error',{}))
        return reply['data']


class RpcError(RuntimeError):
    def __init__(self,error):super().__init__(error.get('message','RPC rejected'));self.code=error.get('code')
