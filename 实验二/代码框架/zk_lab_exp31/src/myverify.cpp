#include <fstream>
#include <iostream>

#include <libsnark/zk_proof_systems/ppzksnark/r1cs_gg_ppzksnark/r1cs_gg_ppzksnark.hpp>

#include "common.hpp"

int main() {
  configure_libsnark_profiling_from_env();
  protoboard<FieldT> pb = build_protoboard(nullptr);

  std::fstream f_vk("vk.raw", std::ios_base::in);
  r1cs_gg_ppzksnark_verification_key<libff::default_ec_pp> vk;
  f_vk >> vk;
  f_vk.close();

  std::fstream f_proof("proof.raw", std::ios_base::in);
  r1cs_gg_ppzksnark_proof<libff::default_ec_pp> proof;
  f_proof >> proof;
  f_proof.close();

  bool verified = false;
  {
    StdoutSilencer silencer(!zk_profiling_enabled());
    verified = r1cs_gg_ppzksnark_verifier_strong_IC<default_r1cs_gg_ppzksnark_pp>(vk, pb.primary_input(), proof);
  }

  std::cout << "验证结果: " << verified << std::endl;
  return 0;
}
