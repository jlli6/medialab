from multiprocessing import Queue, Process 
import imageio
import os
import time

def to_file(res_path, q_input):
    cnt = 0
    while True:
        pic = q_input.get()
        # imageio.imwrite(res_path + str(cnt+1).zfill(3) + ".png", pic)
        cnt = cnt + 1

def test_to_file():
    pic = imageio.imread("./pics/crop/001.png")
    q_test_input = Queue()
    q_test_input.put(pic)

    p_from_file = Process(target=to_file, args=("./res/", q_test_input,))
    p_from_file.start()

    time.sleep(1)

    os.system("ffmpeg -i ./pics/crop/001.png -i ./res/001.png -lavfi psnr -f null -")

    p_from_file.kill()
