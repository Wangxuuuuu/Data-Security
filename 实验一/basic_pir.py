from phe import paillier
import random

def basic_pir_experiment():
    print("=== 基础实验：基于Paillier算法实现隐私信息获取 ===")
    
    # ---------------------------------------------------------
    # 1. 准备阶段
    # ---------------------------------------------------------
    # 服务器端保存的数值
    message_list = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    length = len(message_list)
    print(f"[服务器] 拥有的数据列表: {message_list}\n")
    
    # ---------------------------------------------------------
    # 2. 客户端阶段（1）：生成公私钥，选择要读取的数据位置
    # ---------------------------------------------------------
    public_key, private_key = paillier.generate_paillier_keypair()
    
    # 随机选择一个想要获取的数据位置 (0 到 length-1)
    pos = random.randint(0, length - 1)
    print(f"[客户端] 想要获取的数据索引位置为: {pos} (该位置的实际数值应为 {message_list[pos]})")
    
    # 生成选择向量和密文向量
    select_list = []
    enc_list = []
    for i in range(length):
        # 如果是我们要找的位置，值为1，否则为0
        val = 1 if i == pos else 0
        select_list.append(val)
        # 将0或1进行加密，生成密文
        enc_list.append(public_key.encrypt(val))
        
    print(f"[客户端] 生成的选择向量 (明文): {select_list}")
    print("[客户端] 已将包含多个巨大随机数的密文向量(enc_list)发送给服务器...\n")
    
    # ---------------------------------------------------------
    # 3. 服务器阶段：利用同态特性进行盲运算
    # ---------------------------------------------------------
    print("[服务器] 收到客户端发送的密文请求，开始进行盲运算...")
    c = 0  # 初始累加值
    
    for i in range(length):
        # 核心逻辑：数据值 * 密文
        # 如果密文里藏的是 0，那么 x * E(0) = E(0)
        # 如果密文里藏的是 1，那么 x * E(1) = E(x)
        c = c + message_list[i] * enc_list[i]
        
    print(f"[服务器] 产生最终密文：{c.ciphertext()}")
    print("[服务器] 已将计算后的这串密文返回给客户端...\n")
    
    # ---------------------------------------------------------
    # 4. 客户端阶段（2）：解密结果
    # ---------------------------------------------------------
    print("[客户端] 收到服务器返回的密文，使用私钥进行解密...")
    m = private_key.decrypt(c)
    print(f"[客户端] 最终解密得到的数值: {m}")
    
    if m == message_list[pos]:
         print("\n=> 【实验成功！】客户端成功获取了指定位置的数据，且在这个过程中，由于发送的都是密文，服务器根本不知道客户端获取的是哪一个数据。")
    else:
         print("\n=> 【实验失败！】")

if __name__ == "__main__":
    basic_pir_experiment()
