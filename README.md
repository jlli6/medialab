# IBC视频会议系统

## 代码说明

会议系统包括人脸系统和音频系统两部分。主函数为mymain1.py,主函数中分别为人脸系统和音频系统编写了进程，并且通过队列synchronization 进行同步。

### 人脸系统

人脸系统实现人脸图像的获取，编解码，传输以及显示，包括以下函数：
ingest.py 通过摄像头捕捉图片，并通过队列进行进程间通信。
kpextract.py 使用深度学习模型进行非关键帧图片的关键点提取。
encoding.py 实现了关键帧和关键点的编解码。
pipeIO.py 将编码后的数据写入发端fifo，用于发送；从收端fifo读取接收到的数据，用于解码。
transport.py 使用基于QUIC的收发模块进行传输，关键帧和关键点分开发送。
generate.py 使用深度学习模型从关键帧和关键点数据中重建出非关键帧。
render.py 将解码后的关键帧和重建的非关键帧以固定帧率在窗口播放。
control.py 使用 QUIC 反馈的的网络信息动态调整信源码率。

### 音频系统

音频系统包括两部分功能：（1）实现声音信号的获取，编解码，传输以及播放；（2）调用chatgpt在本地实现实时问答。

音频传输部分包括以下函数：
ingestAudio.py 从麦克风收集音频，并且通过队列发送给编码模块。（一进两出，分别进行编码传输和语音转文字）
encodingAudio.py 调用lyra编码器的C++接口进行音频编解码
pipeIOAudio.py 将编码后的音频数据写入发端fifo，用于发送；从收端fifo读取接收到的音频数据，用于解码。
transportAudio.py 使用基于QUIC的收发模块进行传输。
renderAudioOnly.py 在收端播放解码后的音频。

chatgpt 问答系统包括以下函数：
ingestAudio.py 从麦克风收集音频，发送给语音转文字进程。
STT.py 使用讯飞接口将语音转成文字，在文字信息检测到特定符号（程序中设置为‘秘书’二字）时，会使用websocket将文字信息发送给chatgpt,并得到chatgpt给出的文字回答，保存在xml文件中。最后使用命令行执行tts.py
tts.py ；使用讯飞接口将xml文件中的文字回答转换成mp3音频。

