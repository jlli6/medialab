from multiprocessing import Queue, Process

def encode(q_input, q_output):
    while (True):
        q_output.put(q_input.get())

def decode(q_input, q_output):
    while (True):
        q_output.put(q_input.get())

def test():
    q_test_encoding = Queue()
    q_test_decoding = Queue()
    q_test_output = Queue()

    p_test_encoding = Process(target=encode, args=(q_test_encoding, q_test_decoding,))
    p_test_decoding = Process(target=decode, args=(q_test_decoding, q_test_output,))

    p_test_encoding.start()
    p_test_decoding.start()

    f = open("test", mode="r")
    for line in f:
        q_test_encoding.put(line)
        result = q_test_output.get()
        if line == result:
            print("pass")
        else:
            print("not pass")
            print(line)
            print(result)
    
    f.close()
    p_test_encoding.kill()
    p_test_decoding.kill()