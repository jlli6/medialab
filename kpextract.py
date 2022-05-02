import yaml
import sys
import torch
import os
import imageio
import time
import numpy as np
from skimage.transform import resize
from multiprocessing import Queue, Process
sys.path.append("./LB-FOM")
from modules.keypoint_detector import KPDetector
from sync_batchnorm import DataParallelWithCallback

def extract(q_input, q_output, key_frame_freq=5):
    # load model
    config_path = "./LB-FOM/config/dfdc-256-no-jac.yaml"
    checkpoint_path = "./LB-FOM/model/00000169-checkpoint_finetune.pth.tar"

    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    kp_detector = KPDetector(
        **config["model_params"]["kp_detector_params"],
        **config["model_params"]["common_params"],
    )
    kp_detector.cuda()
    checkpoint = torch.load(checkpoint_path)
    kp_detector.load_state_dict(checkpoint["kp_detector"])
    kp_detector = DataParallelWithCallback(kp_detector)
    kp_detector.eval()

    def kpextract(pic):
        driving_pic = resize(pic, (256, 256))[..., :3]
        with torch.no_grad():
            driving_frame = torch.tensor(driving_pic[np.newaxis].astype(np.float32)).permute(0, 3, 1, 2)
            driving_frame = driving_frame.cuda()
            kp_driving = kp_detector(driving_frame, quanti=False, train=False)
        return kp_driving

    begin = time.time()
    cnt = 0
    extract_time = 0
    while True:
        if cnt % key_frame_freq == 0:
            q_output.put(q_input.get())
        else:
            data = q_input.get()
            frame_begin = time.time()
            kp = kpextract(data)["value"].cpu()[0].numpy()
            # print("kp", cnt, time.time() - frame_begin, flush=True)
            extract_time += time.time() - frame_begin
            q_output.put(kp)
        cnt = cnt + 1
        if cnt == 906:
            end = time.time()
            print("extract ", end - begin, "average ", extract_time / cnt, flush=True)

def test():
    q_test_input = Queue()
    q_test_output = Queue()
    p_kpextract = Process(target=extract, args=(q_test_input, q_test_output, 5))
    p_kpextract.start()

    for i in range(6):
        pic = imageio.imread("./pics/crop/" + str(i+1).zfill(3) + ".png")
        q_test_input.put(pic)
    
    for i in range(6):
        pic = q_test_output.get()
        if i % 5 == 0:
            imageio.imwrite("result.png", pic)
            os.system(f"ffmpeg -i ./pics/crop/{str(i+1).zfill(3)}.png -i result.png -lavfi psnr -f null -")
            os.system("rm result.png")
        else:
            print(pic)
        print(i)
    
    p_kpextract.kill()
