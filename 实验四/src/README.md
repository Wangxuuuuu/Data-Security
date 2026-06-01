执行安装顺序：

```c++
apt install mysql-server libmysqlclient-dev //安装mysql
mysql //测试mysql是否正确
CREATE USER 'user'@'%' IDENTIFIED BY '123456';//sql创建用户
CREATE database test_db //建数据库
pip3 install pycryptodome pymysql -i https://pypi.tuna.tsinghua.edu.cn/simple //这里实验指导书写错了，应该是pymysql，一般只有执行这个，python3和pip3都是自带的
//然后就是把那几个文件复制粘贴，没啥可说的
g++ -shared -fPIC UDF.cpp Node.cpp -o libfhope.so //这里实验指导书也写的不对
sudo cp libfhope.so /usr/lib/mysql/plugin/ //复制到指定目录

# 1. 重启 MySQL，清空 UDF 内存中的 B+ 树
sudo service mysql restart

# 2. 重新导入 SQL，清空 example 表并重建 UDF 注册
mysql -uuser -p123456 test_db < load.sql

# 3. 确认表已为空（应显示 0）
mysql -uuser -p123456 test_db -e "SELECT COUNT(*) FROM example;"

# 4. 再运行教材测试
python3 client.py //运行client.py
    
```

改了一点client.py的内容，让他输出一点log，这样能推断出节点插在哪里了