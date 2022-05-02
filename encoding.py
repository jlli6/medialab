from multiprocessing import Queue, Process
import numpy as np
import av
import os
import imageio
import time
from skimage.transform import resize

data_len = 20

def encode(q_input, q_output, key_frame_freq):
    def quantization(data_ori):
        def quant(data, ori_min, ori_max, tar_min, tar_max):
            return (((data - ori_min) * (tar_max-tar_min) / (ori_max-ori_min)) + tar_min).astype(np.int16)

        data_quant = data_ori.reshape(data_len)
        data_quant = quant(data_quant, -1, 1, 0, 255)
        return data_quant

    def prediction(data_quant, data_last, cnt):
        data_resi = np.zeros(data_len, dtype=np.int16)
        if cnt == 1:
            data_resi = data_quant.copy()
        else:
            data_resi = data_quant - data_last
        data_last = data_quant.copy()
        return data_resi, data_last
        
    def enc_golomb(data_resi, k=0):

        def dec2bin(x, k):
            bits2 = 0
            bitstream2 = ""
            while (bits2 < k):
                tmp_bin = x % 2
                bitstream2 = str(tmp_bin) + bitstream2
                bits2 = bits2 + 1
                x = x // 2
            return bitstream2

        def zero_exp_golomb(x):
            x = x + 1
            bits1 = 0
            bitstream1 = ""
            while (x != 0):
                tmp_bin = x % 2
                bitstream1 = str(tmp_bin) + bitstream1
                bits1 = bits1 + 1
                x = x // 2
            for i in range(bits1 - 1):
                bitstream1 = "0" + bitstream1
            return bitstream1

        def exp_golomb_enc(x, k):
            y = 0
            if x <= 0:
                y = (-2) * x
            else:
                y = 2 * x - 1
            A = y // (2**k)
            B = y % (2**k)
            bitstream1 = zero_exp_golomb(A)
            bitstream2 = dec2bin(B, k)
            return bitstream1 + bitstream2
        
        data_gol = ""
        for i in range(data_len):
            tmpStr = exp_golomb_enc(data_resi[i], k)
            data_gol = data_gol + tmpStr

        return data_gol

    def binary_str2bytes(s):
        s = '1' + s
        pad_num = 8 - len(s) % 8
        if s[-1] == '0':
            s = s + ('1' * pad_num)
        else:   
            s = s + ('0' * pad_num)
        return int(s, 2).to_bytes(len(s) // 8, byteorder='big')

    # init key frame encoding
    enc_codec = av.Codec("hevc", 'w')
    enc_ctx = enc_codec.create()
    enc_ctx.width = 256
    enc_ctx.height = 256
    enc_ctx.pix_fmt = 'yuv420p'
    enc_ctx.options["x265-params"] = "frame-threads=1:\
        keyint=-1:\
        no-open-gop=1:\
        weightp=0:\
        weightb=0:\
        cutree=0:\
        rc-lookahead=0:\
        bframes=0:\
        scenecut=0:\
        b-adapt=0:\
        repeat-headers=1:\
        crf=25"
    
    # init non-key frame encoding
    data_last = np.zeros(data_len, dtype=np.int16)
    
    begin = time.time()
    cnt = 0
    byte_count = 0
    k_enc_time = 0
    nk_enc_time = 0
    while (True):
        if cnt % key_frame_freq == 0:
            rgb_pic = q_input.get()
            frame_begin = time.time()
            rgb_frame = av.VideoFrame.from_ndarray(rgb_pic, format='rgb24')
            yuv_frame = rgb_frame.reformat(format='yuv420p')
            packet = enc_ctx.encode(yuv_frame)
            # print(packet)
            b = packet[0].to_bytes()
            byte_count += len(b)
            k_enc_time += time.time() - frame_begin
            # print("enc key", cnt, time.time() - frame_begin, len(b), flush=True)
            q_output.put(b)
        else:
            data_ori = q_input.get()
            frame_begin = time.time()
            # print("send ori %s", data_ori, flush=True)
            data_quant = quantization(data_ori)
            # print("send quant %s", data_quant, flush=True)
            data_resi, data_last = prediction(data_quant, data_last, cnt)
            # print("send resi %s", data_resi, flush=True)
            data_gol = enc_golomb(data_resi, k=0)
            # print("send gol %s", data_gol, flush=True)
            data_bin = binary_str2bytes(data_gol)
            # print("send bin %s", data_bin, flush=True)
            # return
            nk_enc_time += time.time() - frame_begin
            # print("enc non-key", cnt, time.time() - frame_begin, len(data_bin))
            byte_count += len(data_bin)
            q_output.put(data_bin)
        cnt = cnt + 1
        if cnt == 906:
            end = time.time()
            print("encoding ", end - begin, "average ", k_enc_time / cnt, nk_enc_time / cnt, flush=True)
            print("encode bytes", byte_count, flush=True)

def decode(q_input, q_output, key_frame_freq):
    def dequantization(data_quant):
        def dequant(data, tar_min, tar_max, ori_min, ori_max):
            return (data - ori_min) * (tar_max - tar_min) / (ori_max-ori_min) + tar_min
            
        data_ori = data_quant.reshape(10, 2)
        data_ori = dequant(data_ori, -1, 1, 0, 255)
        return data_ori

    def recover(data_resi, data_last, cnt):
        data = np.zeros(data_len, dtype=np.int16)
        if cnt == 1:
            data = data_resi.copy()
        else:
            data = data_resi + data_last
        data_last = data.copy()
        return data, data_last

    def dec_golomb(data_gol, k):
        #count continuing zero's num
        def count_zero(pos):
            cnt = -1
            find_one = False
            while not find_one:
                if pos >= len(data_gol):
                    return cnt 
                if data_gol[pos] == '1':
                    find_one = True
                cnt += 1
                pos += 1
            return cnt
        
        # start decode
        end_decode = False
        cur_pos = 0
        data_resi = np.zeros(data_len, dtype=np.int16)
        cnt = 0
        while (not end_decode) and (cnt < data_len):
            zero_num = count_zero(cur_pos)
            tmp_str = data_gol[cur_pos + zero_num : cur_pos + (zero_num * 2 + k + 1)]
            if tmp_str:
                dec_num = int(tmp_str, 2) - 2 ** k
            else:
                dec_num = - 2 ** k
            if (dec_num % 2) == 0:
                dec_num = - dec_num / 2
            else:
                dec_num = (dec_num + 1) / 2
            
            if abs(dec_num) > 255:
                dec_num = 0

            data_resi[cnt] = dec_num
            cnt = cnt + 1

            if (cur_pos + (zero_num * 2 + k + 1)) == len(data_gol):
                end_decode = True
            
            cur_pos = cur_pos + (zero_num * 2 + k + 1)

        return data_resi

    def bytes2binary_str(b):
        s = bin(int.from_bytes(b, "big"))[3:]
        # remove padded 0/1
        if s[-1] == '0':
            if '1' in s:
                s = s[:s.rindex('1') + 1]
        else:
            if '0' in s:
                s = s[:s.rindex('0') + 1]
        return s

    # init key frame decoding
    dec_codec = av.Codec("hevc")
    dec_ctx = dec_codec.create()
    frames = []

    # init non-key frame encoding
    data_last = np.zeros(data_len, dtype=np.int16)

    begin = time.time()
    cnt = 0
    k_dec_time = 0
    nk_dec_time = 0
    while (True):
        if cnt % key_frame_freq == 0:
            while not frames:
                packet = av.packet.Packet(q_input.get())
                # print(packet)
                frame_begin = time.time()
                frames = dec_ctx.decode(packet)
            frame = frames.pop(0)
            # print(frames, flush=True)
            frame = frame.reformat(format='rgb24')
            k_dec_time += time.time() - frame_begin
            # print("dec key", cnt, time.time() - frame_begin)
            q_output.put(frame.to_ndarray())
        else:
            # q_output.put(q_input.get())
            data_bin = q_input.get()
            frame_begin = time.time()
            # print("receive bin %s", data_bin)
            data_gol = bytes2binary_str(data_bin)
            # print("receive gol %s", data_gol)
            data_resi = dec_golomb(data_gol, 0)
            # print("receive resi %s", data_resi)
            data_quant, data_last = recover(data_resi, data_last, cnt)
            # print("receive quant %s", data_quant)
            data_ori = dequantization(data_quant)
            # print("receive ori %s", data_ori)
            # return
            nk_dec_time += time.time() - frame_begin
            # print("dec non-key", cnt, time.time() - frame_begin)
            q_output.put(data_ori)
        cnt = cnt + 1
        if cnt == 906:
            end = time.time()
            print("decoding ", end - begin, "average ", k_dec_time / cnt, nk_dec_time / cnt, flush=True)

def test():
    def compare(ori, rec):
        diff = abs(ori - rec).max()
        return diff < 0.1

    q_test_encoding = Queue()
    q_test_decoding = Queue()
    q_test_output = Queue()

    p_test_encoding = Process(target=encode, args=(q_test_encoding, q_test_decoding, 5))
    p_test_decoding = Process(target=decode, args=(q_test_decoding, q_test_output, 5))

    p_test_encoding.start()
    p_test_decoding.start()

    pic = imageio.imread("./pics/crop/001.png")
    q_test_encoding.put(pic)
    point1 = np.array([[-0.29995272, -0.41500735],
        [-0.1831193 , -0.4941489 ],
        [ 0.17194158, -0.02667506],
        [ 0.27690977, -0.57377136],
        [-0.08036794,  0.64549434],
        [-0.12413598, -0.5141814 ],
        [ 0.02390239,  0.1053941 ],
        [ 0.01737955,  0.8387395 ],
        [ 0.10470815,  0.36350307],
        [-0.18321006,  0.63568604]])
    q_test_encoding.put(point1)
    point2 = np.array([[-0.31107202, -0.4134046 ],
        [-0.19297837, -0.49424404],
        [ 0.16959237, -0.02490935],
        [ 0.27347967, -0.57262707],
        [-0.07985441,  0.65166545],
        [-0.12969008, -0.5119384 ],
        [ 0.01797307,  0.10420455],
        [ 0.01933212,  0.8386648 ],
        [ 0.10187937,  0.36533636],
        [-0.18098857,  0.64667803]])
    q_test_encoding.put(point2)
    point3 = np.array([[-0.31828535, -0.41295305],
        [-0.1977081 , -0.49448925],
        [ 0.16152754, -0.02694203],
        [ 0.26536   , -0.57589686],
        [-0.08598499,  0.65046614],
        [-0.13402188, -0.511879  ],
        [ 0.00829535,  0.10598138],
        [ 0.00964345,  0.8365848 ],
        [ 0.09859097,  0.3668807 ],
        [-0.18879706,  0.64301157]])
    q_test_encoding.put(point3)
    point4 = np.array([[-0.32165393, -0.4150526 ],
        [-0.19993302, -0.49823737],
        [ 0.16241762, -0.0259697 ],
        [ 0.2668095 , -0.57577544],
        [-0.08554569,  0.6539978 ],
        [-0.13409549, -0.5143306 ],
        [ 0.0088184 ,  0.10389032],
        [ 0.01263414,  0.83522844],
        [ 0.09746552,  0.36876327],
        [-0.18604723,  0.6528257 ]])
    q_test_encoding.put(point4)
    point = [point1, point2, point3, point4]
    pic = imageio.imread("./pics/crop/006.png")
    q_test_encoding.put(pic)

    for cnt in range(6):
        if cnt % 5 == 0:
            pic = q_test_output.get()
            pic_num = str(cnt+1).zfill(3)
            imageio.imwrite("rec" + pic_num + ".png", pic)
            os.system(f"ffmpeg -i ./pics/crop/{pic_num}.png -i rec{pic_num}.png -lavfi psnr -f null -")
            # os.system(f"rm rec{pic_num}.png")
        else:
            point_rec = q_test_output.get()
            if not compare(point[cnt-1], point_rec):
                print(point[cnt-1])
                print(point_rec)
            else:
                print('pass', cnt)

    p_test_encoding.kill()
    p_test_decoding.kill()