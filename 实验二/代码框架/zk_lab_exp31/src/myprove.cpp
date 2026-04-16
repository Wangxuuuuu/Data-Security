#include <fstream>
#include <iostream>

#include <libsnark/zk_proof_systems/ppzksnark/r1cs_gg_ppzksnark/r1cs_gg_ppzksnark.hpp>

#include "common.hpp"

int main() {
  configure_libsnark_profiling_from_env();
  int x = 0;
  std::cout << "请输入私密值 x: " << std::flush;
  std::cin >> x;
  // 如果是脚本用管道/重定向喂入输入值，为了截图更直观，这里回显读取到的 x。
  if (!::isatty(STDIN_FILENO)) {
    std::cout << x << std::endl;
  } else {
    std::cout << std::endl;
  }

  int secret[4];
  secret[0] = x;
  secret[1] = x * x;
  secret[2] = x * x * x;
  secret[3] = secret[2] + x;

  protoboard<FieldT> pb = build_protoboard(secret);

  std::fstream f_pk("pk.raw", std::ios_base::in);
  r1cs_gg_ppzksnark_proving_key<libff::default_ec_pp> pk;
  f_pk >> pk;
  f_pk.close();

  const r1cs_gg_ppzksnark_proof<default_r1cs_gg_ppzksnark_pp> proof = [&]() {
    StdoutSilencer silencer(!zk_profiling_enabled());
    return r1cs_gg_ppzksnark_prover<default_r1cs_gg_ppzksnark_pp>(pk, pb.primary_input(), pb.auxiliary_input());
  }();

  std::fstream pr("proof.raw", std::ios_base::out);
  pr << proof;
  pr.close();

  std::cout << "证明生成完成：proof.raw" << std::endl;
  return 0;
}
