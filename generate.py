import yaml
import sys
import torch
import time
import imageio
import numpy as np
from skimage.transform import resize
from multiprocessing import Queue, Process
sys.path.append("./LB-FOM")
from modules.generator import OcclusionAwareGenerator
from modules.keypoint_detector import KPDetector
from sync_batchnorm import DataParallelWithCallback

pic_num = 906

def generate(q_input, q_output, key_frame_freq=5):
    # load model
    config_path = "./LB-FOM/config/dfdc-256-no-jac.yaml"
    checkpoint_path = "./LB-FOM/model/00000169-checkpoint_finetune.pth.tar"

    with open(config_path) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    generator = OcclusionAwareGenerator(
        **config["model_params"]["generator_params"], **config["model_params"]["common_params"]
    )
    generator.cuda()
    kp_detector = KPDetector(
        **config["model_params"]["kp_detector_params"],
        **config["model_params"]["common_params"],
    )
    kp_detector.cuda()
    checkpoint = torch.load(checkpoint_path)
    generator.load_state_dict(checkpoint["generator"])
    kp_detector.load_state_dict(checkpoint["kp_detector"])
    generator = DataParallelWithCallback(generator)
    kp_detector = DataParallelWithCallback(kp_detector)
    generator.eval()
    kp_detector.eval()

    begin = time.time()
    cnt = 0
    frame_time = 0
    while True:
        if cnt % key_frame_freq == 0:
            begin_5f = time.time()
            if not cnt == 0:
                last_key_frame = current_key_frame
            current_key_frame = q_input.get()
            if cnt == 0:
                source_image1 = resize(current_key_frame, (256, 256))[..., :3]
                with torch.no_grad():
                    source1 = torch.tensor(source_image1[np.newaxis].astype(np.float32)).permute(0, 3, 1, 2)
                    source1 = torch.cat((source1, source1, source1, source1), 0)
                    source1 = source1.cuda()
                    kp_source1 = kp_detector(source1, quanti=False, train=False)
            else:
                source_image2 = resize(current_key_frame, (256, 256))[..., :3]
                with torch.no_grad():
                    source2 = torch.tensor(source_image2[np.newaxis].astype(np.float32)).permute(0, 3, 1, 2)
                    source2 = torch.cat((source2, source2, source2, source2), 0)
                    # source = torch.cat((source1, source2), 0)

                    source2 = source2.cuda()
                    
                    kp_source2 = kp_detector(source2, quanti=False, train=False)
                    kp_driving = torch.tensor(non_key_frames[0][np.newaxis, :])
                    for frame_idx in range(len(non_key_frames) -  1):
                        kp_driving = torch.cat((kp_driving, torch.tensor(non_key_frames[frame_idx + 1][np.newaxis, :])), 0)
                    
                    # kp_driving = torch.cat((kp_driving, kp_driving), 0)
                    
                    kp_driving = kp_driving.cuda().float()
                    
                    kp_driving = {"value" : kp_driving}
                    
                    predictions = []
                    # start_infer = time.time()
                    # torch.cuda.synchronize()
                    # out = generator(source, kp_source=kp_source, kp_driving=kp_driving)
                    if not cnt == key_frame_freq:
                        last_out1 = out1
                        last_out2 = out2
                    out1 = generator(source1, kp_source=kp_source1, kp_driving=kp_driving)
                    out2 = generator(source2, kp_source=kp_source2, kp_driving=kp_driving)

                    if not cnt == key_frame_freq:
                        # torch.cuda.synchronize()
                        # end_infer = time.time()
                        # print("infer time: ", end_infer - start_infer, flush=True)
                        prediction1 = np.transpose(last_out1["prediction"].data.cpu().numpy(), [0, 2, 3, 1])
                        prediction2 = np.transpose(last_out2["prediction"].data.cpu().numpy(), [0, 2, 3, 1])
                        
                        for frame_idx in range(len(non_key_frames)):
                            weight1 = (key_frame_freq - frame_idx - 1) / key_frame_freq
                            weight2 = 1 - weight1
                            predictions.append(weight1 * prediction1[frame_idx] + weight2 * prediction2[frame_idx])

                        for generated_frame in predictions:
                            q_output.put(generated_frame)
                        q_output.put(last_key_frame)

                    # last group
                    if cnt == pic_num - 1:
                        # print("shit", cnt)
                        prediction1 = np.transpose(out1["prediction"].data.cpu().numpy(), [0, 2, 3, 1])
                        prediction2 = np.transpose(out2["prediction"].data.cpu().numpy(), [0, 2, 3, 1])
                        
                        for frame_idx in range(len(non_key_frames)):
                            weight1 = (key_frame_freq - frame_idx - 1) / key_frame_freq
                            weight2 = 1 - weight1
                            predictions.append(weight1 * prediction1[frame_idx] + weight2 * prediction2[frame_idx])

                        for generated_frame in predictions:
                            q_output.put(generated_frame)
                        q_output.put(current_key_frame)
                        # cnt = cnt + 1
                
                source1 = source2
                kp_source1 = kp_source2
            
            if cnt == 0:
                q_output.put(current_key_frame)
            non_key_frames = []
            end_5f = time.time()
            frame_time += end_5f - begin_5f
            # print("generate 5f ", end_5f - begin_5f, flush=True)
        else:
            non_key_frames.append(q_input.get())
        cnt = cnt + 1
        # print(cnt)
        if cnt == 906:
            end = time.time()
            print("generate ", end - begin, "average ", frame_time, flush=True)

def test():
    q_test_input = Queue()
    q_test_output = Queue()
    p_generate = Process(target=generate, args=(q_test_input, q_test_output, 5))
    p_generate.start()

    pic = imageio.imread("./pics/crop/001.png")
    q_test_input.put(pic)
    point = np.array([[-0.29995272, -0.41500735],
        [-0.1831193 , -0.4941489 ],
        [ 0.17194158, -0.02667506],
        [ 0.27690977, -0.57377136],
        [-0.08036794,  0.64549434],
        [-0.12413598, -0.5141814 ],
        [ 0.02390239,  0.1053941 ],
        [ 0.01737955,  0.8387395 ],
        [ 0.10470815,  0.36350307],
        [-0.18321006,  0.63568604]])
    q_test_input.put(point)
    point = np.array([[-0.31107202, -0.4134046 ],
        [-0.19297837, -0.49424404],
        [ 0.16959237, -0.02490935],
        [ 0.27347967, -0.57262707],
        [-0.07985441,  0.65166545],
        [-0.12969008, -0.5119384 ],
        [ 0.01797307,  0.10420455],
        [ 0.01933212,  0.8386648 ],
        [ 0.10187937,  0.36533636],
        [-0.18098857,  0.64667803]])
    q_test_input.put(point)
    point = np.array([[-0.31828535, -0.41295305],
        [-0.1977081 , -0.49448925],
        [ 0.16152754, -0.02694203],
        [ 0.26536   , -0.57589686],
        [-0.08598499,  0.65046614],
        [-0.13402188, -0.511879  ],
        [ 0.00829535,  0.10598138],
        [ 0.00964345,  0.8365848 ],
        [ 0.09859097,  0.3668807 ],
        [-0.18879706,  0.64301157]])
    q_test_input.put(point)
    point = np.array([[-0.32165393, -0.4150526 ],
        [-0.19993302, -0.49823737],
        [ 0.16241762, -0.0259697 ],
        [ 0.2668095 , -0.57577544],
        [-0.08554569,  0.6539978 ],
        [-0.13409549, -0.5143306 ],
        [ 0.0088184 ,  0.10389032],
        [ 0.01263414,  0.83522844],
        [ 0.09746552,  0.36876327],
        [-0.18604723,  0.6528257 ]])
    q_test_input.put(point)
    pic = imageio.imread("./pics/crop/006.png")
    q_test_input.put(pic)
    
    for i in range(6):
        pic = q_test_output.get()
        imageio.imwrite(f"result{i}.png", pic)
    
    p_generate.kill()
