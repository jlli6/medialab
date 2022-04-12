import os
from multiprocessing import Process
import time

def run(quic_path, mode = "oneway", target_ip = "0.0.0.0", target_port = "1114", receive_port = "1114"):
    def quic_server(path, ip="0.0.0.0", port="1114"):
        os.chdir(path)
        os.system("./server " + ip + " " + port + " > /dev/null")

    def quic_client(path, port="1114"):
        os.chdir(path)
        os.system("./client 127.0.0.1 " + port + " > /dev/null")

    p_quic_server = Process(target=quic_server, args=(quic_path, target_ip, target_port,))
    p_quic_client = Process(target=quic_client, args=(quic_path, receive_port,))

    p_quic_server.start()
    time.sleep(1)
    p_quic_client.start()