#!/usr/bin/env python

import simpy
from hwsim_utils import *
#from GearboxI_proto_I_run_round import Gearbox_I
from GearboxII_new_jupmVC import Gearbox_II
from packet import Packet_descriptior
from queues import *

class Pkt_sched(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period, ptr_in_pipe, ptr_out_pipe, pkt_mon_rdy, vc_upd_pipe, drop_pipe):
        super(Pkt_sched, self).__init__(env, line_clk_period, sys_clk_period)
        self.ptr_in_pipe = ptr_in_pipe
        self.ptr_out_pipe = ptr_out_pipe
        self.pkt_mon_rdy = pkt_mon_rdy

        # 12312020 Peixuan: test vc
        self.vc_upd_pipe = vc_upd_pipe
        #self.blevel_vc_upd_pipe = simpy.Store(env) # 01202021 Peixuan blevel vc
        self.gearbox_vc_upd_pipe = simpy.Store(env) # 01202021 Peixuan gearbox vc
        self.drop_pipe = drop_pipe
        
        self.vc = 0
        #self.prev_fifo = 0

        # gearbox enque pipe
        self.gb_enq_pipe_cmd = simpy.Store(env)
        self.gb_enq_pipe_sts = simpy.Store(env)
        self.gb_deq_pipe_req = simpy.Store(env)
        self.gb_deq_pipe_dat = simpy.Store(env)
        #self.find_earliest_fifo_pipe_req = simpy.Store(env)
        #self.find_earliest_fifo_pipe_dat = simpy.Store(env)
        #self.fifo_num = fifo_num
        fifo_num_list = [10, 10, 10]
        granularity_list = [1, 10, 100]
        fifo_size_list = [128, 128, 128]
        pifo_size_list = [8, 8, 8]
        pifo_thresh_list = [4, 4, 4]

        # instantiate the Base_Level object
        
        self.gearbox = Gearbox_II(env, line_clk_period, sys_clk_period, \
                                self.gb_enq_pipe_cmd, self.gb_enq_pipe_sts, self.gb_deq_pipe_req, self.gb_deq_pipe_dat, \
                                self.gearbox_vc_upd_pipe, self.drop_pipe, \
                                granularity_list, fifo_num_list, fifo_size_list, pifo_size_list, pifo_thresh_list,\
                                fifo_check_latency=1, initial_vc=0)

        #self.ptr_list = list() # remove
        
        self.run()

    def run(self):
        self.env.process(self.sched_enq())
        self.env.process(self.sched_deq())
        self.env.process(self.vc_update_p())

    def sched_enq(self):
        prev_fin_time_lst = [0] * 4
        while True:
            (head_seg_ptr, meta_ptr, tuser) = yield self.ptr_out_pipe.get()
            #self.ptr_list.append((head_seg_ptr, meta_ptr, tuser))
            print ('@ {:.2f} - Enqueue: head_seg_ptr = {} , meta_ptr = {}, tuser = {}'.\
                   format(self.env.now, head_seg_ptr, meta_ptr, tuser))
            flow_id = tuser.pkt_id[0]
            fin_time = max(prev_fin_time_lst[flow_id], self.vc) + tuser.rank
            #if self.blevel.fifo_num > (fin_time - self.vc):
            #    prev_fin_time_lst[flow_id] = fin_time # update prev_fin_time
            tuser_out = Tuser(tuser.pkt_len, fin_time, tuser.pkt_id)
            print ('@ {:.2f} - Enqueue: tuser_out = {}'.\
                   format(self.env.now, tuser_out))
            pkt_des = Packet_descriptior(head_seg_ptr, meta_ptr, tuser_out)
            print ('@ {} - pushed pkt {} with rank = {}'.format(self.env.now, pkt_des.get_uid(), pkt_des.get_finish_time(debug=True)))
            self.gb_enq_pipe_cmd.put(pkt_des)

            enq_success = yield self.gb_enq_pipe_sts.get()  # Enqued: return True; pkt dropped: return False

            if enq_success:
                prev_fin_time_lst[flow_id] = fin_time # update prev_fin_time


    def sched_deq(self):
        while True:
            # wait rdy from pkt mon
            yield self.pkt_mon_rdy.get()
            print ("got ready from pkt mon")

            while True:
                # wait for 10 cycles
                #for j in range(10):
                yield self.wait_sys_clks(1)

                if self.gearbox.get_pkt_cnt() > 0:
                    ##current_fifo_index = self.blevel.get_cur_fifo()

                    # 12312020 Peixuan test
                    '''if not self.prev_fifo == current_fifo_index:
                        self.prev_fifo = current_fifo_index
                        self.vc = self.vc + self.blevel.granularity
                        #for i in range(4): # TODO: already known magic number
                        #    self.vc_upd_pipe.put(self.vc)
                        self.vc_upd_pipe.put(self.vc)
                        self.blevel.update_vc(self.vc)
                        print("updated pkt_sched vc = {}".format(self.vc)) # Peixuan debug'''

                    ##self.find_earliest_fifo_pipe_req.put(current_fifo_index)
                    ##deque_fifo = yield self.find_earliest_fifo_pipe_dat.get()
                    ##self.deq_pipe_req.put(deque_fifo)
                    self.gb_deq_pipe_req.put(1)     # put anything here to request for a deque
                    data = yield self.gb_deq_pipe_dat.get()
                    #print ("*****Data from scheduler is: {}".format(data))
                    pkt_des = data[0] # TODO: why this data is a tuple <pkt, 0>
                    #print ('@ {} - From fifo {}, dequed pkt {} with rank = {}'.format(self.env.now, deque_fifo, pkt_des.get_uid(), pkt_des.get_finish_time(debug=True)))
                    print ('@ {} - From Gearbox dequed pkt {} with rank = {}'.format(self.env.now, pkt_des.get_uid(), pkt_des.get_finish_time(debug=True)))
                    
                    '''# update vc
                    pkt_ft = pkt_des.get_finish_time(0) # TODO: do we need this debug? # 01062020 Peixuan: only update vc from top level
                    #self.blevel.update_vc(pkt_ft)                                      # 01062020 Peixuan: only update vc from top level
                    #print("Updated blevel vc = {}".format(self.blevel.vc)) # Peixuan debug
                    if self.vc < pkt_ft:
                        self.vc = pkt_ft
                        self.vc_upd_pipe.put(self.vc)
                        self.blevel_vc_upd_pipe.put(self.vc)
                        print("updated pkt_sched vc = {}".format(self.vc)) # Peixuan debug'''


                    #((head_seg_ptr, meta_ptr, tuser)) = self.ptr_list.pop(0)
                    head_seg_ptr = pkt_des.get_hdr_addr()
                    meta_ptr = pkt_des.get_meta_addr()
                    tuser = pkt_des.get_tuser()
                
                    print ('@ {:.2f} - Dequeue: head_seg_ptr = {} , meta_ptr = {}, tuser = {}'.format(self.env.now, head_seg_ptr, meta_ptr, tuser))
                    # submit read request
                    self.ptr_in_pipe.put((head_seg_ptr, meta_ptr, tuser))
    
    def vc_update_p(self):
        while True:
            updated_vc = yield self.gearbox_vc_upd_pipe.get()
            self.vc = updated_vc
            print ("updated pkt_sched vc = {}".format(self.vc))


