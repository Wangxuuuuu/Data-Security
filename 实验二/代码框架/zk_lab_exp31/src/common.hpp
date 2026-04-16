#pragma once

#include <cstdlib>
#include <cstdio>

#include <fcntl.h>
#include <unistd.h>

#include <libff/common/profiling.hpp>
#include <libsnark/common/default_types/r1cs_gg_ppzksnark_pp.hpp>
#include <libsnark/gadgetlib1/pb_variable.hpp>
#include <libsnark/relations/constraint_satisfaction_problems/r1cs/r1cs.hpp>

using namespace libsnark;

typedef libff::Fr<default_r1cs_gg_ppzksnark_pp> FieldT;

inline bool zk_profiling_enabled() {
  const char *env = std::getenv("ZK_PROFILING");
  return (env != nullptr && env[0] == '1');
}

inline void configure_libsnark_profiling_from_env() {
  // libsnark 会通过 libff::enter_block/leave_block 输出大量 profiling 信息。
  // 为了输出更简洁，默认关闭；如需开启可设置环境变量：ZK_PROFILING=1
  const bool enable = zk_profiling_enabled();
  libff::inhibit_profiling_info = !enable;
  libff::inhibit_profiling_counters = !enable;
  if (enable) {
    libff::start_profiling();
  }
}

class StdoutSilencer {
 public:
  explicit StdoutSilencer(const bool enabled) : enabled_(enabled) {
    if (!enabled_) {
      return;
    }

    std::fflush(stdout);

    saved_fd_ = ::dup(STDOUT_FILENO);
    if (saved_fd_ < 0) {
      enabled_ = false;
      return;
    }

    const int null_fd = ::open("/dev/null", O_WRONLY);
    if (null_fd < 0) {
      ::close(saved_fd_);
      saved_fd_ = -1;
      enabled_ = false;
      return;
    }

    ::dup2(null_fd, STDOUT_FILENO);
    ::close(null_fd);
  }

  ~StdoutSilencer() {
    if (!enabled_) {
      return;
    }
    std::fflush(stdout);
    ::dup2(saved_fd_, STDOUT_FILENO);
    ::close(saved_fd_);
  }

  StdoutSilencer(const StdoutSilencer &) = delete;
  StdoutSilencer &operator=(const StdoutSilencer &) = delete;

 private:
  bool enabled_ = false;
  int saved_fd_ = -1;
};

inline protoboard<FieldT> build_protoboard(const int *secret) {
  default_r1cs_gg_ppzksnark_pp::init_public_params();

  protoboard<FieldT> pb;

  pb_variable<FieldT> out;
  pb_variable<FieldT> x;
  pb_variable<FieldT> w_1;
  pb_variable<FieldT> w_2;
  pb_variable<FieldT> w_3;

  // 先分配公开输入变量，因为 set_input_sizes(1) 会将第一个变量标记为公开输入。
  out.allocate(pb, "out");
  x.allocate(pb, "x");
  w_1.allocate(pb, "w_1");
  w_2.allocate(pb, "w_2");
  w_3.allocate(pb, "w_3");

  pb.set_input_sizes(1);
  pb.val(out) = 35;

  // x * x = w_1
  pb.add_r1cs_constraint(r1cs_constraint<FieldT>(x, x, w_1));
  // w_1 * x = w_2
  pb.add_r1cs_constraint(r1cs_constraint<FieldT>(w_1, x, w_2));
  // (w_2 + x) * 1 = w_3
  pb.add_r1cs_constraint(r1cs_constraint<FieldT>(w_2 + x, 1, w_3));
  // (w_3 + 5) * 1 = out
  pb.add_r1cs_constraint(r1cs_constraint<FieldT>(w_3 + 5, 1, out));

  if (secret != nullptr) {
    pb.val(x) = secret[0];
    pb.val(w_1) = secret[1];
    pb.val(w_2) = secret[2];
    pb.val(w_3) = secret[3];
  }

  return pb;
}
