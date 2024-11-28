# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import numpy as np
from legacy_test.test_collective_api_base import (
    TestCollectiveAPIRunnerBase,
    dump_output,
    runtime_main,
)

import paddle
from paddle import base
from paddle.distributed.utils import moe_utils

paddle.enable_static()


class TestCollectiveGlobalScatterAPI(TestCollectiveAPIRunnerBase):
    def __init__(self):
        self.global_ring_id = 0

    def get_model(self, main_prog, startup_program, rank, indata=None):
        with base.program_guard(main_prog, startup_program):
            seed = os.getpid()
            np.random.seed(seed)
            in_feat = 2
            n_expert = 2
            world_size = 2
            tot_expert = n_expert * world_size
            local_input_buf = paddle.static.data(
                name="local_input_buf", shape=[-1, in_feat], dtype="float32"
            )
            local_expert_count = paddle.static.data(
                name="local_expert_count", shape=[tot_expert], dtype="int64"
            )
            global_expert_count = []
            paddle.distributed.alltoall(
                global_expert_count, paddle.split(local_expert_count, 2, axis=0)
            )
            global_expert_count = paddle.concat(global_expert_count, axis=0)
            output = moe_utils.global_scatter(
                local_input_buf, local_expert_count, global_expert_count
            )
            return [output]

    def get_model_new_comm(self, main_prog, startup_program, rank, indata=None):
        with base.program_guard(main_prog, startup_program):
            seed = os.getpid()
            np.random.seed(seed)
            in_feat = 2
            n_expert = 2
            world_size = 2
            tot_expert = n_expert * world_size
            local_input_buf = paddle.static.data(
                name="local_input_buf", shape=[-1, in_feat], dtype="float32"
            )
            local_expert_count = paddle.static.data(
                name="local_expert_count", shape=[tot_expert], dtype="int64"
            )
            global_expert_count = []
            paddle.distributed.alltoall(
                global_expert_count,
                paddle.split(local_expert_count, 2, axis=0),
            )
            global_expert_count = paddle.concat(global_expert_count, axis=0)
            output = moe_utils.global_scatter(
                local_input_buf, local_expert_count, global_expert_count
            )
            return [output]

    def run_trainer(self, args):
        train_prog = base.Program()
        startup_prog = base.Program()
        endpoints = args["endpoints"].split(",")
        rank = args["trainerid"]
        current_endpoint = args["currentendpoint"]
        nranks = 2
        if args["dynamic_static_unified_comm"]:
            paddle.distributed.collective._init_parallel_env(args["backend"])
        else:
            paddle.distributed.init_parallel_env()
        if args['backend'] == 'nccl':
            device_id = int(os.getenv("FLAGS_selected_gpus", "0"))
            place = base.CUDAPlace(
                device_id
            )  # if args.use_gpu else base.CPUPlace()
        elif args['backend'] == 'bkcl':
            device_id = int(os.getenv("FLAGS_selected_xpus", "0"))
            place = base.XPUPlace(device_id)
        else:
            place = base.CPUPlace()
        np.random.seed(os.getpid())
        in_feat = 2
        n_expert = 2
        world_size = 2
        tot_expert = n_expert * world_size
        local_expert_count = np.random.randint(1, 4, size=tot_expert).astype(
            "int64"
        )
        fwd_expert_count = sum(local_expert_count)
        local_input_buf = np.random.rand(fwd_expert_count, in_feat).astype(
            "float32"
        )
        if args['static_mode']:
            result = (
                self.get_model_new_comm(train_prog, startup_prog, rank)
                if args["dynamic_static_unified_comm"]
                else self.get_model(train_prog, startup_prog, rank)
            )
            exe = base.Executor(place)
            exe.run(startup_prog)
            fetch_list = []
            for elem in result:
                fetch_list.append(elem.name)
            out = exe.run(
                train_prog,
                feed={
                    'local_expert_count': local_expert_count,
                    'local_input_buf': local_input_buf,
                },
                fetch_list=fetch_list,
            )

        dump_output(out)


if __name__ == "__main__":
    runtime_main(TestCollectiveGlobalScatterAPI, "global_scatter")
