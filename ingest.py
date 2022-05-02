import imageio
import os
import time
from multiprocessing import Queue, Process

def from_file(pic_path, q_ouput, pic_num):
    cnt = 0
    while cnt < 90:
        cnt = cnt + 1
        q_ouput.put(imageio.imread(pic_path + str(cnt).zfill(3) + ".png"))
        time.sleep(0.04)

def test_from_file():
    q_test_output = Queue()
    p_from_file = Process(target=from_file, args=("./pics/crop/", q_test_output, 1,))
    p_from_file.start()

    pic = q_test_output.get()
    imageio.imwrite("result.png", pic)
    os.system("ffmpeg -i ./pics/crop/001.png -i result.png -lavfi psnr -f null -")
    os.system("rm result.png")

    p_from_file.kill()