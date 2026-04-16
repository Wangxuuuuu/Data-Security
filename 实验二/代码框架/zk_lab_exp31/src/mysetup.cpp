#include <fstream>
#include <iostream>

#include <libsnark/zk_proof_systems/ppzksnark/r1cs_gg_ppzksnark/r1cs_gg_ppzksnark.hpp>

#include "common.hpp"

int main() {
  configure_libsnark_profiling_from_env();
  protoboard<FieldT> pb = build_protoboard(nullptr);
  const r1cs_constraint_system<FieldT> constraint_system = pb.get_constraint_system();

  const r1cs_gg_ppzksnark_keypair<default_r1cs_gg_ppzksnark_pp> keypair = [&]() {
    StdoutSilencer silencer(!zk_profiling_enabled());
    return r1cs_gg_ppzksnark_generator<default_r1cs_gg_ppzksnark_pp>(constraint_system);
  }();

  std::fstream pk("pk.raw", std::ios_base::out);
  pk << keypair.pk;
  pk.close();

  std::fstream vk("vk.raw", std::ios_base::out);
  vk << keypair.vk;
  vk.close();

  std::cout << "初始化完成：已生成 pk.raw 和 vk.raw" << std::endl;
  return 0;
}
