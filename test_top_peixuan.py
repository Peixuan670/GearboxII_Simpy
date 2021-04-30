#!/usr/bin/env python

import simpy
from hwsim_utils import *
from pkt_gen import *
from pkt_mux import *
from packet_storage import *
#from pkt_sched_blevel import *
#from pkt_sched_gearbox import *
from pkt_sched_gearboxII import *
#from pkt_sched_gearbox_onelevel import *
from pkt_mon import *

class Top_tb(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period):
        super(Top_tb, self).__init__(env, line_clk_period, sys_clk_period)
        self.num_flows = 4
        self.ptr_in_pipe = simpy.Store(env)
        self.ptr_out_pipe = simpy.Store(env)
        self.drop_pipe = simpy.Store(env)
        self.sched_vc_pipe = simpy.Store(env) # 12312020 Peixuan test
        self.pkt_gen_pipes = [simpy.Store(env)] * self.num_flows
        self.pkt_mux_pipe = simpy.Store(env)
        self.pkt_store_pipe = simpy.Store(env)
        self.pkt_mon_rdy = simpy.Store(env)

        self.bit_rates = [1 * 10**9, 1 * 10**9, 1 * 10**9, 1 * 10**9]
        #self.bit_rates = [1 * 10**8, 1 * 10**8, 1 * 10**8, 1 * 10**8]
        self.weights = [1, 1, 0.1, 0.1]
        self.quantum = 64 # bytes
        self.num_test_pkts = [150, 150, 150, 150]
        #self.num_test_pkts = [15, 15, 15, 15]

        self.pkt_gen = list()
        for f in range(self.num_flows):
            self.pkt_gen = Pkt_gen(env, line_clk_period, sys_clk_period, \
                                   self.pkt_gen_pipes[f], f, self.bit_rates[f], self.weights[f], self.quantum, \
                                   self.num_test_pkts[f])
        self.pkt_mux = Pkt_mux(env, line_clk_period, sys_clk_period, self.pkt_gen_pipes, self.pkt_mux_pipe)
        self.pkt_store = Pkt_storage(env, line_clk_period, sys_clk_period, self.pkt_mux_pipe, \
                                     self.pkt_store_pipe, self.ptr_in_pipe, self.ptr_out_pipe, self.drop_pipe)
        self.pkt_sched = Pkt_sched(env, line_clk_period, sys_clk_period, self.ptr_in_pipe, \
                                  self.ptr_out_pipe, self.pkt_mon_rdy, self.sched_vc_pipe, self.drop_pipe)
        self.pkt_mon = Pkt_mon(env, line_clk_period, sys_clk_period, self.pkt_store_pipe, \
                               self.num_flows, self.num_test_pkts, self.pkt_mon_rdy)
        
        self.vc = 0
        
        self.run()

    def run(self):
        self.env.process(self.top_tb())

    def top_tb(self):
        while True:
            updated_vc = yield self.sched_vc_pipe.get()
            self.vc = updated_vc
            print ("Top VC: {0}".format(self.vc))
            print("updated top vc = {}".format(self.vc)) # Peixuan debug
        
def main():
    env = simpy.Environment(0.0)
    line_clk_period = 0.1 * 8 # 0,1 ns/bit * 8 bits
    sys_clk_period = 3 # ns (200 MHz)
    # instantiate the testbench
    ps_tb = Top_tb(env, line_clk_period, sys_clk_period)
    # run the simulation 
    env.run(until=1500000)

if __name__ == "__main__":
    main()

