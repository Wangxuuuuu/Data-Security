from phe import paillier
import random
from cryptography.fernet import Fernet

def extended_pir_experiment():
    print("=== 扩展实验：结合对称加密的隐私信息获取 ===\n")
    
    # =========================================================
    # 步骤 1: 客户端生成对称密钥，并准备初始数据
    # =========================================================
    print("--- [阶段 1: 数据准备与对称加密] ---")
    # 客户端生成对称密钥 k (使用 Fernet)
    symmetric_key = Fernet.generate_key()
    cipher_suite = Fernet(symmetric_key)
    print(f"[客户端] 生成对称密钥 k: {symmetric_key}")
    
    # 假设我们有以下这些敏感信息的明文列表（字符串）
    plaintext_list = [
        "Confidential Data A", 
        "Confidential Data B", 
        "Confidential Data C", 
        "Confidential Data D", 
        "Confidential Data E"
    ]
    length = len(plaintext_list)
    print(f"[数据源] 原始明文数据: {plaintext_list}\n")
    
    # 客户端（或数据拥有者）将数据用对称密钥加密，并转换为大整数，然后存放到服务器
    server_database = []
    for pt in plaintext_list:
        # 1. 字符串转 utf-8 bytes
        pt_bytes = pt.encode('utf-8')
        # 2. 用对称密钥进行 AES 加密，得到密文 bytes
        enc_bytes = cipher_suite.encrypt(pt_bytes)
        # 3. 【核心技术点】：将密文 bytes 转换为大整数，因为 Paillier 只能处理数字！
        enc_int = int.from_bytes(enc_bytes, byteorder='big')
        server_database.append(enc_int)
        
    print("[服务器] 已接收并存储了用客户端密钥加密后的数据 (以大整数形式保存):")
    for i, data in enumerate(server_database):
        print(f"  索引 {i}: {str(data)[:20]}... (省略过长数字)")
    print()


    # =========================================================
    # 步骤 2: 客户端发起隐私获取请求 (过程与基础实验几乎一样)
    # =========================================================
    print("--- [阶段 2: 客户端发起 PIR 请求] ---")
    public_key, private_key = paillier.generate_paillier_keypair()
    
    # 客户端想获取索引为 2 的数据 (即 "Confidential Data C")
    pos = 2
    print(f"[客户端] 想要获取的数据索引位置为: {pos}")
    
    select_list = []
    enc_list = []
    for i in range(length):
        val = 1 if i == pos else 0
        select_list.append(val)
        enc_list.append(public_key.encrypt(val))
        
    print("[客户端] 已将加密后的选择向量发送给服务器...\n")


    # =========================================================
    # 步骤 3: 服务器进行盲运算
    # =========================================================
    print("--- [阶段 3: 服务器盲运算] ---")
    print("[服务器] 正在基于同态加密进行安全查询...")
    c = 0
    for i in range(length):
        # 这里的 server_database[i] 虽然是密文，但现在表现为一个大整数
        # 用它去乘以 Paillier 密文，利用同态特性将其累加
        c = c + server_database[i] * enc_list[i]
        
    print("[服务器] 运算完成，将最终的 Paillier 密文返回给客户端。\n")


    # =========================================================
    # 步骤 4: 客户端双重解密拿回明文
    # =========================================================
    print("--- [阶段 4: 客户端双重解密] ---")
    # 第一重解密：Paillier 解密
    retrieved_int = private_key.decrypt(c)
    print(f"[客户端] 1. 通过 Paillier 私钥解密，得到大整数: {str(retrieved_int)[:20]}...")
    
    # 第二重解密：对称解密
    # 1. 先把大整数转换回密文 bytes
    # 计算大整数需要多少个 byte 才能装下
    byte_length = (retrieved_int.bit_length() + 7) // 8  
    retrieved_bytes = retrieved_int.to_bytes(byte_length, byteorder='big')
    
    # 2. 使用对称密钥解密恢复明文
    try:
        decrypted_pt_bytes = cipher_suite.decrypt(retrieved_bytes)
        final_plaintext = decrypted_pt_bytes.decode('utf-8')
        print(f"[客户端] 2. 通过对称密钥 k 解密，成功还原明文: >>> {final_plaintext} <<<")
        
        if final_plaintext == plaintext_list[pos]:
            print("\n=> 【扩展实验成功！】成功在服务器端不清楚查询意图、且数据本身被对称加密保护的双重安全环境下，获取了目标数据！")
    except Exception as e:
        print(f"\n=> 【实验失败】对称解密出错: {e}")

if __name__ == "__main__":
    extended_pir_experiment()