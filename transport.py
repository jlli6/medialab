import os
from multiprocessing import Process
import time

def run(quic_path, remote_ip="0.0.0.0", remote_port="1114", local_port="1114"):
    def quic_server(path, port="1114"):
        os.chdir(path)
        os.system("./server 0.0.0.0 "+ port + " > /dev/null")

    def quic_client(path, ip="127.0.0.1", port="1114"):
        os.chdir(path)
        os.system("./client " + ip + " " + port + " > /dev/null")

    p_quic_server = Process(target=quic_server, args=(quic_path, local_port,))
    p_quic_client = Process(target=quic_client, args=(quic_path, remote_ip, remote_port,))

    p_quic_server.start()
    time.sleep(4)
    p_quic_client.start()
