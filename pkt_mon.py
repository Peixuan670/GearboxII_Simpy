#!/usr/bin/env python

import simpy
from hwsim_utils import *
from packet_storage import *
from scapy.all import *

class Pkt_mon(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period, pkt_out_pipe, num_flows, num_pkts, pkt_mon_rdy):
        super(Pkt_mon, self).__init__(env, line_clk_period, sys_clk_period)
        self.pkt_out_pipe = pkt_out_pipe
        self.num_flows = num_flows
        self.num_pkts = num_pkts
        self.pkt_mon_rdy = pkt_mon_rdy
        
        self.pkt_mon_lst = [(0, None)] * 2
        self.run()

    def run(self):
        self.env.process(self.pkt_mon_queue())
        self.env.process(self.pkt_mon_sm())

    def pkt_mon_queue(self):
        i = 0
        while True:
            # signal pkt mon ready to scheduler
            self.pkt_mon_rdy.put(1)
            # wait to receive output pkt and metadata
            (pkt_out, tuser_out) = yield self.pkt_out_pipe.get()
            # store packet and metadata in list
            self.pkt_mon_lst[i] = (1, (pkt_out, tuser_out))
            # flip index
            if i == 0:
                i = 1
            else:
                i = 0
            # Wait until there's room in the queue
            while (self.pkt_mon_lst[0][0] == 1 and self.pkt_mon_lst[1][0] == 1):
                yield self.wait_sys_clks(1)
                
    def pkt_mon_sm(self):
        i = 0
        pkt_lst = [[] for j in range(self.num_flows)]
        rank_lst = []
        for j in range(sum(self.num_pkts)):
            # Wait until there's a packet in the queue
            while (self.pkt_mon_lst[i][0] == 0):
                yield self.wait_sys_clks(1)
            # get packet from queue
            (pkt_out, tuser_out) = self.pkt_mon_lst[i][1]
            self.pkt_mon_lst[i] = (0, (0, 0))
            print ('@ {:.2f} - Receive: {} || {}'.format(self.env.now, pkt_out.summary(), tuser_out))
            # collect per flow info
            rank = tuser_out.rank
            flow_id = tuser_out.pkt_id[0]
            pkt_num = tuser_out.pkt_id[1]
            print ("pkt rcvd: Rx rank: {} flow_id: {} pkt_num: {}".format(rank, flow_id, pkt_num))
            pkt_lst[flow_id].append(pkt_num)
            rank_lst.append((flow_id, pkt_num, rank))
            # wait number of clocks corresponding to packet preamble, packet length and IFG
            yield self.wait_line_clks(self.PREAMBLE + pkt_out.len + self.IFG)
            # flip index
            if i == 0:
                i = 1
            else:
                i = 0
        # process results
        for j in range (self.num_flows):
            print ("Flow {} pkts: {}".format(j, pkt_lst[j]))
            if len(pkt_lst[j]) != self.num_pkts[j]:
                print ("Received {} packets, expecting {len(pkt_lst[j])} packets".format(self.num_pkts[j]))
            for i in range(len(pkt_lst[j])):
                if pkt_lst[j][i] != i:
                    print ("OOO in flow {}: Expecting packet #{}, received packet #{}".format(j, i, pkt_lst[j][i]))
        #print ("Ranks: {}".format(rank_lst))
        sched_err_cnt = 0
        for i in range(len(rank_lst)-1):
            if rank_lst[i][2] > rank_lst[i+1][2]:
                print ("Scheduler Error: fin time[{}]: f:{} p:{} r:{} > fin time[{}]: f:{} p:{} r:{}".\
                       format(i, rank_lst[i][0], rank_lst[i][1], rank_lst[i][2], \
                              i+1, rank_lst[i+1][0], rank_lst[i+1][1], rank_lst[i+1][2]))
                sched_err_cnt += 1
        if (sched_err_cnt != 0):
            print ("Number of scheduler errors = {}".format(sched_err_cnt))