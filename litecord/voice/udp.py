import asyncio

class UDPVoiceServer:
    """Represents an UDP Voice server.

    Clients connect to this server and it requests data about it
    through :meth:`VoiceServer` so it knows how to route packets
    to the other clients connected to it.

    NOTE: This is not implemented to handle routing whatsoever,
    this is the example UDP echo server from asyncio docs. lol.
    """
    def connection_made(self, transport):
        """Called when a new client connets to the server.
        
        Since each client connects in a specific port, we need to query
        the voice server about data of this guy.
        the question is... how?
        """
        self.transport = transport

    def datagram_received(self, data, addr):
        """This should broadcase your data to the other connected clients.
        
        How though :thinking:
        """
        message = data.decode()
        log.debug(f'Received {message} from {addr}')

        decrypted = self.decrypt(message)
        message = opus.decode(message)

        if message.channels != 2:
            return

        if message.sample_rate != 48000:
            return

        self.transport.sendto(data, addr)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    listen = loop.create_datagram_endpoint(UDPVoiceServer, listen_addr=('localhost', 9696))
    transport, protocol = loop.run_until_complete(listen)
    
    loop.run_forever()
    
    transport.close()
    loop.close()

