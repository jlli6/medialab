import sys, getopt
from multiprocessing import Queue, Process

# lib
import server 
import encoding
import pipeIO

def run_system(mode="run", server_port=8080):
    # data
    q_send_server_encoding = Queue()
    q_send_encoding_pipe = Queue()
    q_receive_pipe_decoding = Queue()
    q_reveive_decoding_server = Queue()

    # process
    p_server = Process(target=server.server, args=(server_port, q_send_server_encoding, q_reveive_decoding_server,))
    p_encoding = Process(target=encoding.encode, args=(q_send_server_encoding, q_send_encoding_pipe,))
    if mode == "test":
        p_pipe = Process(target=pipeIO.test_noFIFO, args=(q_send_encoding_pipe, q_receive_pipe_decoding,))
    elif mode == "oneway":
        p_pipe = Process(target=pipeIO.run_oneway, args=(q_send_encoding_pipe, q_receive_pipe_decoding,))
    else:
        p_pipe = Process(target=pipeIO.run, args=(q_send_encoding_pipe, q_receive_pipe_decoding))
    p_decoding = Process(target=encoding.decode, args=(q_receive_pipe_decoding, q_reveive_decoding_server,))

    p_server.start()
    p_encoding.start()
    p_pipe.start()
    p_decoding.start()

    input()

    p_server.kill()
    p_encoding.kill()
    p_pipe.kill()
    p_decoding.kill()

def test_server():
    p_server = Process(target=server.test)
    p_server.start()
    p_server.join()

def test_encoding():
    p_encoding = Process(target=encoding.test)
    p_encoding.start()
    p_encoding.join()

def test_pipe():
    p_pipe = Process(target=pipeIO.test)
    p_pipe.start()
    p_pipe.join() 

if __name__ == "__main__":
    server_port = 8080

    # input
    opts, _ = getopt.getopt(sys.argv[1:], "t:", ["test=", "server_port="])

    if opts:
        # load paras
        for o, a in opts:
            if o in ("--server_port"):
                server_port = int(a)
        # test
        for o, a in opts:
            if o in ("-t", "--test"):
                if a == "system":
                    run_system(mode="test", server_port=server_port)
                elif a == "oneway":
                    run_system(mode="oneway", server_port=server_port)
                elif a == "server":
                    test_server()
                elif a == "encoding":
                    test_encoding()
                elif a == "pipe":
                    test_pipe()
    else:
        run_system(mode="run")
