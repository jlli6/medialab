import sys, getopt
from multiprocessing import Queue, Process
import time

# lib
import ingest
import kpextract
import encoding
import pipeIO
import transport
import generate
import render

def run_system(mode="run", remote_ip="127.0.0.1", remote_port="1114", local_port="1114"):
    # data
    q_send_ingest_keypointextract = Queue()
    q_send_keypointextract_encoding = Queue()
    q_send_encoding_pipe = Queue()
    q_receive_pipe_decoding = Queue()
    q_receive_decoding_generate = Queue()
    q_receive_generate_render = Queue()
    pic_path = "./pics/resize/"
    res_path = "./res/"
    pipe_path = "./pipe/"
    pic_num = 906
    key_frame_freq = 5

    # process
    processes = []
    p_ingest = Process(target=ingest.from_file, args=(pic_path, q_send_ingest_keypointextract, pic_num,))
    processes.append(p_ingest)
    p_kpextract = Process(target=kpextract.extract, args=(q_send_ingest_keypointextract, q_send_keypointextract_encoding, key_frame_freq,))
    processes.append(p_kpextract)
    p_encoding = Process(target=encoding.encode, args=(q_send_keypointextract_encoding, q_send_encoding_pipe, key_frame_freq,))
    processes.append(p_encoding)
    if mode == "noFIFO":
        p_pipe = Process(target=pipeIO.test_noFIFO, args=(q_send_encoding_pipe, q_receive_pipe_decoding,))
        processes.append(p_pipe)
    else:
        p_vsend_pipe = Process(target=pipeIO.write, args=(q_send_encoding_pipe, pipe_path, key_frame_freq,))
        # processes.append(p_vsend_pipe)
        p_transport = Process(target=transport.run, args=(pipe_path, remote_ip, remote_port, local_port,))
        # processes.append(p_transport)
        p_vreceive_pipe = Process(target=pipeIO.read, args=(q_receive_pipe_decoding, pipe_path, key_frame_freq,))
        # processes.append(p_vreceive_pipe)
        p_vsend_pipe.start()
        p_vreceive_pipe.start()
        time.sleep(0.1)
        p_transport.start()

    p_decoding = Process(target=encoding.decode, args=(q_receive_pipe_decoding, q_receive_decoding_generate, key_frame_freq))
    processes.append(p_decoding)
    p_generate = Process(target=generate.generate, args=(q_receive_decoding_generate, q_receive_generate_render ,key_frame_freq,))
    processes.append(p_generate)
    p_render = Process(target=render.to_file, args=(res_path, q_receive_generate_render,))
    processes.append(p_render)

    time.sleep(3)

    for process in processes:
        process.start()

    input()

    for process in processes:
        process.kill()

def test_ingest():
    p_ingest = Process(target=ingest.test_from_file)
    p_ingest.start()
    p_ingest.join()

def test_kpextract():
    p_kpextract = Process(target=kpextract.test)
    p_kpextract.start()
    p_kpextract.join()

def test_encoding():
    p_encoding = Process(target=encoding.test)
    p_encoding.start()
    p_encoding.join()

def test_pipe():
    p_pipe = Process(target=pipeIO.test)
    p_pipe.start()
    p_pipe.join() 
    
def test_generate():
    p_generate = Process(target=generate.test)
    p_generate.start()
    p_generate.join() 

def test_render():
    p_render = Process(target=render.test_to_file)
    p_render.start()
    p_render.join() 

if __name__ == "__main__":
    remote_ip = "0.0.0.0"
    remote_port = "1114"
    local_port = "1114"
    test_flag = False

    # input
    opts, _ = getopt.getopt(sys.argv[1:], "t:", ["test=", "remote_ip=", "remote_port=", "local_port="])

    if opts:
        # load paras
        for o, a in opts:
            if o in ("--remote_ip"):
                remote_ip = a
            if o in ("--remote_port"):
                remote_port = a
            if o in ("--local_port"):
                local_port = a
        # test
        for o, a in opts:
            if o in ("-t", "--test"):
                test_flag = True
                if a == "ingest":
                    test_ingest()
                elif a == "kpextract":
                    test_kpextract()  
                elif a == "encoding":
                    test_encoding()
                elif a == "pipe":
                    test_pipe() 
                elif a == "generate":
                    test_generate()
                elif a == "render":
                    test_render()
                elif a == "noFIFO":
                    run_system(mode="noFIFO", remote_ip=remote_ip, remote_port=remote_port, local_port=local_port)
        if not test_flag:
            run_system(mode="run", remote_ip=remote_ip, remote_port=remote_port, local_port=local_port)
    else:
        print("Error: no params. Use --test to enter test mode. Add --remote_ip to enter run mode.")
