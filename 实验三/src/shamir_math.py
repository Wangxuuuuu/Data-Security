import random

# 使用经典的大素数，保证安全性且防止溢出
PRIME = 1000000007

def generate_shares(secret, n, k):
    """
    根据 Shamir (k, n) 门限方案生成 n 个分享碎片。
    """
    # 随机生成多项式的系数，常数项为 secret
    coefficients = [secret] + [random.randint(1, PRIME - 1) for _ in range(k - 1)]
    
    shares = []
    for x in range(1, n + 1):
        # 计算多项式在 x 处的值 y = (c0 + c1*x + c2*x^2 + ...) mod PRIME
        y = sum(c * pow(x, i, PRIME) for i, c in enumerate(coefficients)) % PRIME
        shares.append((x, y))
        
    return shares

def reconstruct_secret(shares):
    """
    使用拉格朗日插值法从 k 个碎片中重构秘密。
    shares: 包含 (x, y) 元组的列表
    """
    secret = 0
    for i, (x_i, y_i) in enumerate(shares):
        numerator = 1
        denominator = 1
        for j, (x_j, _) in enumerate(shares):
            if i != j:
                numerator = (numerator * (0 - x_j)) % PRIME
                denominator = (denominator * (x_i - x_j)) % PRIME
                
        # 使用 Python 内置的 pow 函数和费马小定理快速求逆元（替代复杂的 quickpower）
        lagrange_coeff = (numerator * pow(denominator, PRIME - 2, PRIME)) % PRIME
        secret = (secret + y_i * lagrange_coeff) % PRIME
        
    return secret
