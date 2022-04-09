from multiprocessing import Queue, Process
import json
import numpy as np

intra_period = 10
data_len = 9

def encode(q_input, q_output):

    def quantization(data_ori):
        data_quant = np.zeros(data_len, dtype=np.int16)

        def quant(data, ori_min, ori_max, tar_min, tar_max):
            return round((data - ori_min) * (tar_max-tar_min) / (ori_max-ori_min)) + tar_min
            
        data_quant[0] = quant(data_ori["pupil"]["x"], -2, 2, 0, 4095)
        data_quant[1] = quant(data_ori["pupil"]["y"], -2, 2, 0, 4095)
        data_quant[2] = quant(data_ori["head"]["degrees"]["x"], -180, 180, 0, 4095)
        data_quant[3] = quant(data_ori["head"]["degrees"]["y"], -180, 180, 0, 4095)
        data_quant[4] = quant(data_ori["head"]["degrees"]["z"], -180, 180, 0, 4095)
        data_quant[5] = quant(data_ori["eye"]["l"], 0, 1, 0, 4095)
        data_quant[6] = quant(data_ori["eye"]["r"], 0, 1, 0, 4095)
        data_quant[7] = quant(data_ori["mouth"]["x"], -0.6, 1.4, 0, 4095)
        data_quant[8] = quant(data_ori["mouth"]["y"], 0, 1, 0, 4095)
        return data_quant

    def prediction(data_quant, data_last, cnt):
        data_resi = np.zeros(data_len, dtype=np.int16)
        if cnt % intra_period == 0:
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

    def enc_binary(data_gol):

        def binary_str2bytes(s):
            pad_num = 8 - len(s) % 8
            if s[-1] == '0':
                s = s + ('1' * pad_num)
            else:   
                s = s + ('0' * pad_num)
            return int(s, 2).to_bytes(len(s) // 8, byteorder='big')

        ## bitNum represents the bit number of bins
        def float2bin(float_num, bit_num):
            bins = []
            for _ in range(bit_num):
                float_num = float_num * 2
                if float_num >= 1.0:
                    bins.append(1)
                else:
                    bins.append(0)
                float_num -= int(float_num)
            return bins
    
        def bin2float(bins):
            float_num = 0.0
            for i in range(len(bins)):
                float_num += int(bins[i]) * (2**(-i-1))
            return float_num
        
        ## rescale the low boundary and high boundary
        def enc_rescale(low, high):
            low_bin = float2bin(low, 64)
            high_bin = float2bin(high, 64)
            end = False
            out_bins = ""
            
            while not end:
                if low_bin[0] == high_bin[0]:
                    out_bins += str(low_bin[0])
                    low_bin.pop(0)
                    high_bin.pop(0)
                else:
                    end = True
            
            new_low = bin2float(low_bin)
            new_high = bin2float(high_bin)
            
            return out_bins, new_low, new_high
        
        ## start Binary encode
        low = 0.0
        high = 1.0
        r = high - low # the length of interval
        bit0_num = bit1_num = 1
        p0 = p1 = 0.5
        
        data_bin = ""
        
        for c in data_gol:
            if c == '0':
                high = high - r*p1
                if high != 1.0:
                    out_bins, low, high = enc_rescale(low, high)
                    data_bin += out_bins
                r = high - low
                bit0_num += 1
            else:
                low = low + r*p0
                if high != 1.0:
                    out_bins, low, high = enc_rescale(low, high)
                    data_bin += out_bins
                r = high - low
                bit1_num += 1
            ## some corner case
            if high == 0.5 or low == 0.5:
                high += 0.1
                low += 0.1
            p0 = bit0_num / (bit1_num + bit0_num)
            p1 = 1- p0
        
        ## find a middle number
        mid = low + r/2
        mid_bin = float2bin(mid, 64)
        end_enc = False
        cur_pos = 1
        while not end_enc:
            mid_num = bin2float(mid_bin[0: cur_pos])
            if (mid_num > low) and (mid_num < high):
                end_enc = True
            else:
                cur_pos += 1
        
        for i in range(cur_pos):
            data_bin += str(mid_bin[i])

        return binary_str2bytes(data_bin)

    
    cnt = 0
    data_last = np.zeros(data_len, dtype=np.int16)

    while (True):
        # q_output.put(q_input.get())
        json_data = q_input.get()
        data_ori = json.loads(json_data)
        # print("send ori %s", data_ori)
        data_quant = quantization(data_ori)
        # print("send quant %s", data_quant)
        data_resi, data_last = prediction(data_quant, data_last, cnt)
        # print("send resi %s", data_resi)
        data_gol = enc_golomb(data_resi, k=0)
        # print("send gol %s", data_gol)
        data_bin = enc_binary(data_gol)
        # print("send bin %s", data_bin)
        # return
        q_output.put(data_bin)
        cnt = cnt + 1

def decode(q_input, q_output):
    
    def dequantization(data_quant):

        def dequant(data, tar_min, tar_max, ori_min, ori_max):
            return (data - ori_min) * (tar_max - tar_min) / (ori_max-ori_min) + tar_min
            
        data_ori = {}
        data_ori["pupil"] = {}
        data_ori["pupil"]["x"] = dequant(data_quant[0], -2, 2, 0, 4095)
        data_ori["pupil"]["y"] = dequant(data_quant[1], -2, 2, 0, 4095)
        data_ori["head"] = {}
        data_ori["head"]["degrees"] = {}
        data_ori["head"]["degrees"]["x"] = dequant(data_quant[2], -180, 180, 0, 4095)
        data_ori["head"]["degrees"]["y"] = dequant(data_quant[3], -180, 180, 0, 4095)
        data_ori["head"]["degrees"]["z"] = dequant(data_quant[4], -180, 180, 0, 4095)
        data_ori["eye"] = {}
        data_ori["eye"]["l"] = dequant(data_quant[5], 0, 1, 0, 4095)
        data_ori["eye"]["r"] = dequant(data_quant[6], 0, 1, 0, 4095)
        data_ori["mouth"] = {}
        data_ori["mouth"]["x"] = dequant(data_quant[7], -0.6, 1.4, 0, 4095)
        data_ori["mouth"]["y"] = dequant(data_quant[8], 0, 1, 0, 4095)
        return data_ori

    def recover(data_resi, data_last, cnt):
        data = np.zeros(data_len, dtype=np.int16)
        if cnt % intra_period == 0:
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
        while (not end_decode) and (cnt < 9):
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
            
            if abs(dec_num) > 4095:
                dec_num = 0

            data_resi[cnt] = dec_num
            cnt = cnt + 1

            if (cur_pos + (zero_num * 2 + k + 1)) == len(data_gol):
                end_decode = True
            
            cur_pos = cur_pos + (zero_num * 2 + k + 1)

        return data_resi

    def dec_binary(data_bin):
        dec_bin_end = False

        def bytes2binary_str(b):
            s = bin(int.from_bytes(b, "big"))[2:]
            # count lost 0 in head
            zero_loss_num = 8 - len(s) % 8
            # remove padded 0/1
            if s[-1] == '0':
                s = s[:s.rindex('1') + 1]
            else:
                s = s[:s.rindex('0') + 1]
            return '0' * zero_loss_num + s + 'a'

        def float2bin(float_num, bit_num):
            bins = []
            for _ in range(bit_num):
                float_num = float_num * 2
                if float_num >= 1.0:
                    bins.append(1)
                else:
                    bins.append(0)
                float_num -= int(float_num)
            return bins
    
        def bin2float(bins):
            float_num = 0.0
            for i in range(len(bins)):
                float_num += int(bins[i]) * (2**(-i-1))
            return float_num
        
        def dec_rescale(enc_str, low, high):
            low_bin = float2bin(low, 64)
            high_bin = float2bin(high, 64)
            end = False
            
            while not end:
                if low_bin[0] == high_bin[0]:
                    low_bin.pop(0)
                    high_bin.pop(0)
                    if len(enc_str) > 0:
                        enc_str.pop(0)
                    else:
                        dec_bin_end = True
                        end = True
                else:
                    end = True
                
            new_low = bin2float(low_bin)
            new_high = bin2float(high_bin)
            
            return enc_str, new_low, new_high
        
        bit1_num = bit0_num = 1
        p0 = p1 = 0.5
        low = 0.0
        high = 1.0
        r = high - low
        
        data_gol = ""
        data_bin = bytes2binary_str(data_bin)
        enc_str = list(data_bin)
        
        repeat_cnt = 0
        last_len = len(enc_str)

        while (not dec_bin_end) and (len(enc_str) > 1) and (repeat_cnt < 200):
            last_len = len(enc_str)
            if len(enc_str) > 64:
                enc_num = bin2float(enc_str[0:64])
            else:
                enc_num = bin2float(enc_str[:-1])
            
            boundary = low + r*p0
            if enc_num > boundary:
                data_gol += '1'
                low = low + r*p0
                if high != 1.0:
                    enc_str, low, high = dec_rescale(enc_str, low, high)
                r = high - low
                bit1_num += 1
            else:
                data_gol += '0'
                high = high - r*p1
                if high != 1.0:
                    enc_str, low, high = dec_rescale(enc_str, low, high)
                r = high - low
                bit0_num += 1
            if high == 0.5 or low == 0.5:
                high += 0.1
                low += 0.1
                r = high - low
            p0 = bit0_num / (bit1_num + bit0_num)
            p1 = 1- p0

            if last_len == len(enc_str):
                repeat_cnt = repeat_cnt + 1
            else:
                repeat_cnt = 0
        
        return data_gol

    cnt = 0
    data_last = np.zeros(data_len, dtype=np.int16)

    while (True):
        # q_output.put(q_input.get())
        data_bin = q_input.get()
        # print("receive bin %s", data_bin)
        data_gol = dec_binary(data_bin)
        # print("receive gol %s", data_gol)
        data_resi = dec_golomb(data_gol, 0)
        # print("receive resi %s", data_resi)
        data_quant, data_last = recover(data_resi, data_last, cnt)
        # print("receive quant %s", data_quant)
        data_ori = dequantization(data_quant)
        # print("receive ori %s", data_ori)
        # return
        json_data = json.dumps(data_ori)
        q_output.put(json_data)
        cnt = cnt + 1

def test():
    def compare(ori, rec):
        if abs(ori["pupil"]["x"] - rec["pupil"]["x"]) > 0.1:
            print("pupil x", ori["pupil"]["x"], rec["pupil"]["x"])
            return False
        if abs(ori["pupil"]["y"] - rec["pupil"]["y"]) > 0.1:
            print("pupil y", ori["pupil"]["y"], rec["pupil"]["y"])
            return False
        if abs(ori["mouth"]["x"] - rec["mouth"]["x"]) > 0.1:
            print("mouth x", ori["mouth"]["x"], rec["mouth"]["x"])
            return False
        if abs(ori["mouth"]["y"] - rec["mouth"]["y"]) > 0.1:
            print("mouth y", ori["mouth"]["y"], rec["mouth"]["y"])
            return False
        if abs(ori["eye"]["l"] - rec["eye"]["l"]) > 0.1:
            print("eye l", ori["eye"]["l"], rec["eye"]["l"])
            return False
        if abs(ori["eye"]["r"] - rec["eye"]["r"]) > 0.1:
            print("eye r", ori["eye"]["r"], rec["eye"]["r"])
            return False
        if abs(ori["head"]["degrees"]["x"] - rec["head"]["degrees"]["x"]) > 1:
            print("head degrees x", ori["head"]["degrees"]["x"], rec["head"]["degrees"]["x"])
            return False
        if abs(ori["head"]["degrees"]["y"] - rec["head"]["degrees"]["y"]) > 1:
            print("head degrees y", ori["head"]["degrees"]["y"], rec["head"]["degrees"]["y"])
            return False
        if abs(ori["head"]["degrees"]["z"] - rec["head"]["degrees"]["z"]) > 1:
            print("head degrees z", ori["head"]["degrees"]["z"], rec["head"]["degrees"]["z"])
            return False
        return True


    q_test_encoding = Queue()
    q_test_decoding = Queue()
    q_test_output = Queue()

    p_test_encoding = Process(target=encode, args=(q_test_encoding, q_test_decoding,))
    p_test_decoding = Process(target=decode, args=(q_test_decoding, q_test_output,))

    p_test_encoding.start()
    p_test_decoding.start()

    cnt = 0
    f = open("test", mode="r")
    for line in f:
        q_test_encoding.put(line)
        result = q_test_output.get()
        if compare(json.loads(line), json.loads(result)):
            print("pass")
        else:
            print("not pass")
            print(cnt)
            # break
        cnt = cnt + 1

    f.close()
    p_test_encoding.kill()
    p_test_decoding.kill()