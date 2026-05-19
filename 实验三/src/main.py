import json
import os
from shamir_math import generate_shares, reconstruct_secret, PRIME

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    # 定义参与者和门限参数
    N = 3 # 参与方数量
    K = 2 # 门限值
    
    # 1. 初始化数据：三个同学各自的秘密数据
    # 这里我们随机预设三个数字，代表需要进行隐私求和并求平均的数据
    secrets = {
        1: 85,  # 同学 1 的数据
        2: 92,  # 同学 2 的数据
        3: 78   # 同学 3 的数据
    }
    print(f"[阶段 1: 数据产生] 学生的真实数据: {secrets}")
    print(f"真实的平均值应为: {sum(secrets.values()) / N:.2f}\n")
    
    # 2. 生成并分发碎片
    # 模拟网络传输通道（信箱），mailbox[i] 代表准备发送给 同学 i 的所有碎片
    mailbox = {1: [], 2: [], 3: []}
    
    for student_id, secret in secrets.items():
        # 生成 (2, 3) 门限的 3 个碎片
        shares = generate_shares(secret, n=N, k=K)
        print(f"同学 {student_id} 生成了 3 份碎片: {shares}")
        
        # 分发碎片：第 i 份碎片发给同学 i
        for i in range(1, N + 1):
            mailbox[i].append(shares[i - 1])
            
    # 将分发过程保存为本地格式化文件，利用JSON整洁地模拟网络数据包传输 (取代大量散乱 txt 文件)
    print("\n[阶段 2: 碎片分发] 正在模拟碎片在网络中的交互传输...")
    json_path = os.path.join(os.path.dirname(__file__), 'communication_simulate.json')
    save_json(json_path, mailbox)
    print(f"碎片的结构化数据包已生成并保存至 {json_path}")
    
    # 3. 隐私求和：各方在本地把收到的碎片加起来
    # 读取网络缓存中的数据 (模拟各方从网络接收到数据包)
    received_mailbox = load_json(json_path)
    aggregate_shares = []
    
    print("\n[阶段 3: 本地计算] 同学各自对收到了网络发来的碎片，并在本地进行同态相加...")
    for student_id_str, shares in received_mailbox.items():
        # 特性：到达每个收集方的多项式碎片，其 x 坐标是一致的，就是接收者的 id
        # 所以只需要对其 y 坐标相加并取模即可
        x_val = int(student_id_str)
        y_sum = sum(share[1] for share in shares) % PRIME
        
        final_share = (x_val, y_sum)
        aggregate_shares.append(final_share)
        print(f"同学 {student_id_str} 本地计算完成，得出的聚合碎片 d{student_id_str} 为: {final_share}")
        
    # 4. 统计与重构：计票员收集聚合结果进行还原
    # 根据(2, 3)门限理论，我们只需任意选用 2 份聚合碎片 (比如选 d1, d2)
    chosen_shares = aggregate_shares[:K]
    print(f"\n[阶段 4: 汇总重构] 汇算节点收集了 {K} 份结果用于重构秘密总和: {chosen_shares}")
    
    total_sum = reconstruct_secret(chosen_shares)
    print(f"-> 【成功】重构出数据的求和总值为: {total_sum}")
    
    # 5. 按照实验目标要求，求平均
    average = total_sum / N
    print(f"-> 【完成】最终计算得出 3 人的数据平均值为: {average:.2f}")

if __name__ == "__main__":
    main()
