import pymysql
import random
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64

local_table = {}
key = get_random_bytes(16)
base_iv = get_random_bytes(16)

# 记录上一步的 encoding 序列，用于观察 Recode（编码批量更新）
prev_encodings = []


def AES_ENC(plaintext, iv):
    aes = AES.new(key, AES.MODE_CBC, iv=iv)
    padded_data = pad(plaintext, AES.block_size, style='pkcs7')
    ciphertext = aes.encrypt(padded_data)
    return ciphertext


def AES_DEC(ciphertext, iv):
    aes = AES.new(key, AES.MODE_CBC, iv=iv)
    padded_data = aes.decrypt(ciphertext)
    plaintext = unpad(padded_data, AES.block_size, style='pkcs7')
    return plaintext


def Random_Encrypt(plaintext):
    iv = get_random_bytes(16)
    ciphertext = AES_ENC(iv + AES_ENC(plaintext.encode('utf-8'), iv), base_iv)
    ciphertext = base64.b64encode(ciphertext)
    return ciphertext.decode('utf-8')


def Random_Decrypt(ciphertext):
    plaintext = AES_DEC(base64.b64decode(ciphertext.encode('utf-8')), base_iv)
    plaintext = AES_DEC(plaintext[16:], plaintext[:16])
    return plaintext.decode('utf-8')


def get_connection():
    return pymysql.connect(
        host='localhost', user='user',
        password='123456', database='test_db'
    )


def CalPos(plaintext):
    presum = sum([v for k, v in local_table.items() if k < plaintext])
    print("本地表之中小于要插入明文的所有明文出现次数总和：", presum)
    if plaintext in local_table:
        local_table[plaintext] += 1
        the_pos = random.randint(presum, presum + local_table[plaintext] - 1)
        print(
            f"要插入的明文已经存在, 选择范围: [{presum}, {presum + local_table[plaintext] - 1}]",
            end=' '
        )
        print("随机选择的位置:", the_pos)
        return the_pos
    else:
        local_table[plaintext] = 1
        print("要插入的明文之前不存在，直接选择位置:", presum)
        return presum


def GetLeftPos(plaintext):
    return sum([v for k, v in local_table.items() if k < plaintext])


def GetRightPos(plaintext):
    return sum([v for k, v in local_table.items() if k <= plaintext])


def observe_encoding_change(new_encodings):
    """对比相邻两次插入后的 encoding，提示是否发生 Recode 或树分裂"""
    global prev_encodings
    new_list = [row[0] for row in new_encodings]

    if not prev_encodings:
        print("[观察] 首次插入，编码树建立")
    elif len(new_list) == len(prev_encodings) + 1:
        # 仅新增一个 encoding，且旧 encoding 未变 → 正常插入
        if prev_encodings == new_list[:-1]:
            print("[观察] 正常插入：新增 1 个 encoding，已有 encoding 未变")
        else:
            print("[观察] 可能发生 Recode：新增记录的同时，部分旧 encoding 被重新分配")
    elif len(new_list) > len(prev_encodings) + 1:
        print("[观察] 异常：记录数增加超过 1，请检查数据库状态")
    elif len(new_list) == len(prev_encodings):
        changed = sum(1 for old, new in zip(prev_encodings, new_list) if old != new)
        if changed > 1:
            print(f"[观察] Recode 触发：{changed} 条记录的 encoding 在同一轮插入中被批量更新")
        elif changed == 1:
            print("[观察] 仅 1 条 encoding 变化（可能为同长度下的局部调整）")
        else:
            print("[观察] encoding 数量未变且数值未变（不应出现，请检查）")

    prev_encodings = new_list


def Insert(plaintext):
    global prev_encodings
    ciphertext = Random_Encrypt(plaintext)
    conn = get_connection()
    cur = conn.cursor()
    the_result = CalPos(plaintext)
    print("插入的明文:", plaintext, "位置:", the_result)
    cur.execute(f"call pro_insert({the_result},'{ciphertext}')")
    conn.commit()

    print("------------此时编码树的结果-------------")
    cur.execute("select encoding from example order by encoding")
    results1 = cur.fetchall()
    for result in results1:
        print(result[0], end=" ")
    print()
    observe_encoding_change(results1)
    conn.close()


def Search(left, right):
    left_pos = GetLeftPos(left)
    right_pos = GetRightPos(right)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"select ciphertext from example where encoding >= FHSearch({left_pos}) and encoding < FHSearch({right_pos})"
    )
    rest = cur.fetchall()
    for x in rest:
        print(f"ciphtertext: {x[0]} \t plaintext: {Random_Decrypt(x[0])}")
    conn.close()


def verify_integrity():
    total = sum(local_table.values())
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("select count(distinct encoding) from example")
    db_count = cur.fetchone()[0]
    conn.close()
    print("local_table:", local_table)
    print("本地表共:", total, "数据项")
    print("现在数据库之中共有:", db_count, "个 distinct encoding")
    if db_count == total:
        print("数据数量一致，实验成功！")
    else:
        print("警告：encoding 数量与本地表不一致，请检查是否未重置环境")


if __name__ == '__main__':
    # 阶段 B：在教材 8 条基础上，大量重复插入 apple / cherry，观察编码树分裂与 Recode
    print("----------------------------------------")
    print("-----阶段 B：重复插入相同值扩展测试-----")
    print("----------------------------------------")
    print("提示：运行前请先执行")
    print("  sudo service mysql restart")
    print("  mysql -uuser -p123456 test_db < load.sql")
    print("----------------------------------------")

    test_data = [
        'apple', 'pear', 'banana', 'orange', 'cherry',
        'apple', 'cherry', 'orange',
        'apple', 'apple', 'apple', 'apple',
        'cherry', 'cherry', 'apple', 'cherry',
    ]

    for plaintext in test_data:
        Insert(plaintext)

    print("----------------------------------------")
    print("-----假设我们搜索 b 和 p 之间的数据-----")
    print("----------------------------------------")
    Search('b', 'p')

    print("----------------------------------------")
    print("----------下面展示本地表内容------------")
    print("----------------------------------------")
    verify_integrity()
