#!/usr/bin/env python

import simpy
from hwsim_utils import *

PKT_FIFO_DEPTH = 256

class Pkt_mux(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period, pkt_in_pipes, pkt_out_pipe):
        super(Pkt_mux, self).__init__(env, line_clk_period, sys_clk_period)
        self.pkt_in_pipes = pkt_in_pipes
        self.num_in_ports = len(pkt_in_pipes)
        self.pkt_out_pipe = pkt_out_pipe
        self.in_fifo = [Fifo(PKT_FIFO_DEPTH)] * self.num_in_ports        
                   
        self.run()

    def run(self):
        for p in range(self.num_in_ports):
            self.env.process(self.push_in_pkts(p))
        self.env.process(self.pkt_mux())
                    
    def push_in_pkts(self, port):
        while True:
            pkt = yield self.pkt_in_pipes[port].get()
            #print ("mux: {0}".format(pkt))
            self.in_fifo[port].push(pkt)
        
    def pkt_mux(self):
        #pkt_lst = list()
        p = 0
        while True:
            if self.in_fifo[p].fill_level() != 0:
                self.pkt_out_pipe.put(self.in_fifo[p].pop())
            yield self.wait_sys_clks(1)
            if p < self.num_in_ports - 1:
                p += 1
            else:
                p = 0
            

