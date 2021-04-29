import math
from hwsim_utils import *
from packet import Packet_descriptior
from queues import FIFO, PIFO
from gearboxII_level import GearboxII_level
from base_level_II import Base_level

# Peixuan 01142020
# This is Gearbox II
# Prototype I: multi_level, has ping pong, no step down
# NOTICE: This prototype is for functional test: each round round only plus 1
class Gearbox_II(HW_sim_object):
    # Public
    def __init__(self, env, line_clk_period, sys_clk_period, \
        gb_enq_pipe_cmd, gb_enq_pipe_sts, gb_deq_pipe_req, gb_deq_pipe_dat, \
        vc_data_pipe, drop_pipe, \
        granularity_list, fifo_num_list, fifo_size_list, pifo_size_list, pifo_thresh_list,\
        fifo_check_latency=1, initial_vc=0):
        super(Gearbox_II, self).__init__(env, line_clk_period, sys_clk_period) # 02232021 Peixuan

        self.env = env
        
        self.granularity_list = granularity_list        # List: granularity of each level
        self.fifo_num_list = fifo_num_list              # List: fifo num of each level
        self.fifo_size_list = fifo_size_list            # List: fifo size of each level
        self.fifo_check_latency = fifo_check_latency    # depreciated

        self.pifo_size_list = pifo_size_list            # List: pifo size of each level
        self.pifo_thresh_list = pifo_thresh_list        # List: pifo reload threshold of each level

        self.enque_latency = 2                          # 02232021 Peixuan: total enque latency = enque_latency + write latency
        self.deque_01_latency = 2                       # 02232021 Peixuan: total enque latency = deque_latency + read latency
        self.deque_02_latency = 4                       # 02232021 Peixuan: total enque latency = deque_latency + read latency

        # Gearbox enque/deque pipes
        self.gb_enq_pipe_cmd = gb_enq_pipe_cmd
        self.gb_enq_pipe_sts = gb_enq_pipe_sts
        self.gb_deq_pipe_req = gb_deq_pipe_req
        self.gb_deq_pipe_dat = gb_deq_pipe_dat

        self.gb_jump_VC_req = simpy.Store(env) # pipe to find next non empty fifo
        self.gb_jump_VC_dat = simpy.Store(env) # pipe to find next non empty fifo

        self.gb_update_VC_req = simpy.Store(env) # pipe to find updated VC
        self.gb_update_VC_dat = simpy.Store(env) # pipe to find updated VC

        self.vc_data_pipe = vc_data_pipe        # vc update pipe (goes to outer module)
        self.drop_pipe = drop_pipe              # pkt drop pipe

        self.vc = initial_vc
        self.pkt_cnt = 0
        self.level_num = 3

        # Initiate all the levels

        # ping pong levels
        self.levelsA = []   # levels, set A (length: level num)
        #self.levelsB = []   # levels, set B (length: level num -1, highest level only in set A)

        # fifo function input/output pipes
        self.fifo_r_in_pipe_matrix_A = []       # Two dimentional matrix
        self.fifo_r_out_pipe_matrix_A = []      # Two dimentional matrix
        self.fifo_w_in_pipe_matrix_A = []       # Two dimentional matrix
        self.fifo_w_out_pipe_matrix_A = []      # Two dimentional matrix

        self.pifo_r_in_pipe_arr_A = []       # One dimentional array
        self.pifo_r_out_pipe_arr_A = []      # One dimentional array
        self.pifo_w_in_pipe_arr_A = []       # One dimentional array
        self.pifo_w_out_pipe_arr_A = []      # One dimentional array

        #self.fifo_r_in_pipe_matrix_B = []       # Two dimentional matrix
        #self.fifo_r_out_pipe_matrix_B = []      # Two dimentional matrix
        #self.fifo_w_in_pipe_matrix_B = []       # Two dimentional matrix
        #self.fifo_w_out_pipe_matrix_B = []      # Two dimentional matrix

        # level function input/output pipes
        # set A
        self.enq_pipe_cmd_arr_A = [] 
        self.enq_pipe_sts_arr_A = []
        self.deq_pipe_req_arr_A = []
        self.deq_pipe_dat_arr_A = []
        self.find_earliest_fifo_pipe_req_arr_A = [] # depreciated
        self.find_earliest_fifo_pipe_dat_arr_A = [] # depreciated

        self.rld_pipe_cmd_arr_A = [] 
        self.rld_pipe_sts_arr_A = [] 
        self.mig_pipe_req_arr_A = [] 
        self.mig_pipe_dat_arr_A = []

        self.mig_enq_pipe_cmd_arr_A = [] 
        self.mig_enq_pipe_sts_arr_A = []

        # set B
        #self.enq_pipe_cmd_arr_B = [] 
        #self.enq_pipe_sts_arr_B = []
        #self.deq_pipe_req_arr_B = []
        #self.deq_pipe_dat_arr_B = []
        #self.find_earliest_fifo_pipe_req_arr_B = [] # depreciated
        #self.find_earliest_fifo_pipe_dat_arr_B = [] # depreciated

        # flags & bytes for deque
        self.deque_bytes = []           # bytes to be served for each level (as index)
        self.deque_served_bytes = []    # bytes already served for each level (as index)

        index = 0
        while (index < self.level_num):
            self.deque_bytes.append(0)          # initialize bytes to deque as 0
            self.deque_served_bytes.append(0)   # initialize bytes dequed as 0
            index = index + 1

        # initiate base level (level 0)
        index = 0   

        fifo_r_in_pipe_arr = []
        fifo_r_out_pipe_arr = []
        fifo_w_in_pipe_arr = []
        fifo_w_out_pipe_arr = []

        fifo_index = 0
        while (fifo_index < self.fifo_num_list[index]):
            fifo_r_in_pipe_arr.append(simpy.Store(env))
            fifo_r_out_pipe_arr.append(simpy.Store(env))
            fifo_w_in_pipe_arr.append(simpy.Store(env))
            fifo_w_out_pipe_arr.append(simpy.Store(env))
            fifo_index = fifo_index + 1
        
        self.fifo_r_in_pipe_matrix_A.append(fifo_r_in_pipe_arr)
        self.fifo_r_out_pipe_matrix_A.append(fifo_r_out_pipe_arr)
        self.fifo_w_in_pipe_matrix_A.append(fifo_w_in_pipe_arr)
        self.fifo_w_out_pipe_matrix_A.append(fifo_w_out_pipe_arr)

        enq_pipe_cmd = simpy.Store(env)
        enq_pipe_sts = simpy.Store(env)
        deq_pipe_req = simpy.Store(env)
        deq_pipe_dat = simpy.Store(env)
        mig_enq_pipe_cmd = simpy.Store(env)
        mig_enq_pipe_sts = simpy.Store(env)
        find_earliest_fifo_pipe_req = simpy.Store(env)
        find_earliest_fifo_pipe_dat = simpy.Store(env)

        self.enq_pipe_cmd_arr_A.append(enq_pipe_cmd)
        self.enq_pipe_sts_arr_A.append(enq_pipe_sts)
        self.deq_pipe_req_arr_A.append(deq_pipe_req)
        self.deq_pipe_dat_arr_A.append(deq_pipe_dat)
        self.mig_enq_pipe_cmd_arr_A.append(mig_enq_pipe_cmd)
        self.mig_enq_pipe_sts_arr_A.append(mig_enq_pipe_sts)
        self.find_earliest_fifo_pipe_req_arr_A.append(find_earliest_fifo_pipe_req)
        self.find_earliest_fifo_pipe_dat_arr_A.append(find_earliest_fifo_pipe_dat)

        # For level 0, pifo-related pipes are initialized as 0s
        self.pifo_r_in_pipe_arr_A.append(0)
        self.pifo_r_out_pipe_arr_A.append(0)
        self.pifo_w_in_pipe_arr_A.append(0)
        self.pifo_w_out_pipe_arr_A.append(0)

        self.rld_pipe_cmd_arr_A.append(0)
        self.rld_pipe_sts_arr_A.append(0)
        self.mig_pipe_req_arr_A.append(0)
        self.mig_pipe_dat_arr_A.append(0)


        self.blevel = Base_level(env, line_clk_period, sys_clk_period, granularity_list[0], fifo_size_list[0], \
                      self.enq_pipe_cmd_arr_A[0], self.enq_pipe_sts_arr_A[0], self.deq_pipe_req_arr_A[0], self.deq_pipe_dat_arr_A[0],\
                      self.mig_enq_pipe_cmd_arr_A[0], self.mig_enq_pipe_sts_arr_A[0], self.drop_pipe, \
                      self.find_earliest_fifo_pipe_req_arr_A[0], self.find_earliest_fifo_pipe_dat_arr_A[0], \
                      self.fifo_r_in_pipe_matrix_A[0], self.fifo_r_out_pipe_matrix_A[0], self.fifo_w_in_pipe_matrix_A[0], self.fifo_w_out_pipe_matrix_A[0], \
                      fifo_write_latency=1, fifo_read_latency=1, fifo_check_latency=1, fifo_num=10, initial_vc=0)
        
        
        # initiate levels for set A
        
        index = 1
        while (index < self.level_num):

            fifo_r_in_pipe_arr = []
            fifo_r_out_pipe_arr = []
            fifo_w_in_pipe_arr = []
            fifo_w_out_pipe_arr = []

            fifo_index = 0
            while (fifo_index < self.fifo_num_list[index]):
                fifo_r_in_pipe_arr.append(simpy.Store(env))
                fifo_r_out_pipe_arr.append(simpy.Store(env))
                fifo_w_in_pipe_arr.append(simpy.Store(env))
                fifo_w_out_pipe_arr.append(simpy.Store(env))
                fifo_index = fifo_index + 1

            self.fifo_r_in_pipe_matrix_A.append(fifo_r_in_pipe_arr)
            self.fifo_r_out_pipe_matrix_A.append(fifo_r_out_pipe_arr)
            self.fifo_w_in_pipe_matrix_A.append(fifo_w_in_pipe_arr)
            self.fifo_w_out_pipe_matrix_A.append(fifo_w_out_pipe_arr)

            self.pifo_r_in_pipe_arr_A.append(simpy.Store(env))
            self.pifo_r_out_pipe_arr_A.append(simpy.Store(env))
            self.pifo_w_in_pipe_arr_A.append(simpy.Store(env))
            self.pifo_w_out_pipe_arr_A.append(simpy.Store(env))

            enq_pipe_cmd = simpy.Store(env)
            enq_pipe_sts = simpy.Store(env)
            deq_pipe_req = simpy.Store(env)
            deq_pipe_dat = simpy.Store(env)
            find_earliest_fifo_pipe_req = simpy.Store(env)
            find_earliest_fifo_pipe_dat = simpy.Store(env)

            rld_pipe_cmd = simpy.Store(env)
            rld_pipe_sts = simpy.Store(env)
            mig_pipe_req = simpy.Store(env)
            mig_pipe_dat = simpy.Store(env)
            mig_enq_pipe_cmd = simpy.Store(env)
            mig_enq_pipe_sts = simpy.Store(env)

            self.enq_pipe_cmd_arr_A.append(enq_pipe_cmd)
            self.enq_pipe_sts_arr_A.append(enq_pipe_sts)
            self.deq_pipe_req_arr_A.append(deq_pipe_req)
            self.deq_pipe_dat_arr_A.append(deq_pipe_dat)
            self.find_earliest_fifo_pipe_req_arr_A.append(find_earliest_fifo_pipe_req)
            self.find_earliest_fifo_pipe_dat_arr_A.append(find_earliest_fifo_pipe_dat)

            self.rld_pipe_cmd_arr_A.append(rld_pipe_cmd)
            self.rld_pipe_sts_arr_A.append(rld_pipe_sts)
            self.mig_pipe_req_arr_A.append(mig_pipe_req)
            self.mig_pipe_dat_arr_A.append(mig_pipe_dat)
            self.mig_enq_pipe_cmd_arr_A.append(mig_enq_pipe_cmd)
            self.mig_enq_pipe_sts_arr_A.append(mig_enq_pipe_sts)

            cur_level = GearboxII_level(env, line_clk_period, sys_clk_period, self.granularity_list[index], self.fifo_size_list[index], \
                self.pifo_size_list[index], self.pifo_thresh_list[index], \
                self.enq_pipe_cmd_arr_A[index], self.enq_pipe_sts_arr_A[index], self.deq_pipe_req_arr_A[index], self.deq_pipe_dat_arr_A[index], \
                self.rld_pipe_cmd_arr_A[index], self.rld_pipe_sts_arr_A[index], self.mig_pipe_req_arr_A[index], self.mig_pipe_dat_arr_A[index], self.mig_enq_pipe_cmd_arr_A[index], self.mig_enq_pipe_sts_arr_A[index],\
                self.enq_pipe_cmd_arr_A[index-1], self.enq_pipe_sts_arr_A[index-1], \
                self.find_earliest_fifo_pipe_req_arr_A[index], self.find_earliest_fifo_pipe_dat_arr_A[index], \
                self.fifo_r_in_pipe_matrix_A[index], self.fifo_r_out_pipe_matrix_A[index], \
                self.fifo_w_in_pipe_matrix_A[index], self.fifo_w_out_pipe_matrix_A[index], \
                self.pifo_r_in_pipe_arr_A[index], self.pifo_r_out_pipe_arr_A[index], \
                self.pifo_w_in_pipe_arr_A[index], self.pifo_w_out_pipe_arr_A[index], \
                fifo_write_latency=1, fifo_read_latency=1, fifo_check_latency=1, fifo_num=10,\
                pifo_write_latency=1, pifo_read_latency=1, pifo_shift_latency=1, initial_vc=0)
            

            self.levelsA.append(cur_level)
            
            index = index + 1
        
        # initiate levels for set B
        
        '''index = 0
        while (index < self.level_num - 1): # Highest level doesn't need ping-pong

            fifo_r_in_pipe_arr = []
            fifo_r_out_pipe_arr = []
            fifo_w_in_pipe_arr = []
            fifo_w_out_pipe_arr = []

            fifo_index = 0
            while (fifo_index < self.fifo_num_list[index]):
                fifo_r_in_pipe_arr.append(simpy.Store(env))
                fifo_r_out_pipe_arr.append(simpy.Store(env))
                fifo_w_in_pipe_arr.append(simpy.Store(env))
                fifo_w_out_pipe_arr.append(simpy.Store(env))
                fifo_index = fifo_index + 1

            self.fifo_r_in_pipe_matrix_B.append(fifo_r_in_pipe_arr)
            self.fifo_r_out_pipe_matrix_B.append(fifo_r_out_pipe_arr)
            self.fifo_w_in_pipe_matrix_B.append(fifo_w_in_pipe_arr)
            self.fifo_w_out_pipe_matrix_B.append(fifo_w_out_pipe_arr)

            enq_pipe_cmd = simpy.Store(env)
            enq_pipe_sts = simpy.Store(env)
            deq_pipe_req = simpy.Store(env)
            deq_pipe_dat = simpy.Store(env)
            find_earliest_fifo_pipe_req = simpy.Store(env)
            find_earliest_fifo_pipe_dat = simpy.Store(env)

            self.enq_pipe_cmd_arr_B.append(enq_pipe_cmd)
            self.enq_pipe_sts_arr_B.append(enq_pipe_sts)
            self.deq_pipe_req_arr_B.append(deq_pipe_req)
            self.deq_pipe_dat_arr_B.append(deq_pipe_dat)
            self.find_earliest_fifo_pipe_req_arr_B.append(find_earliest_fifo_pipe_req)
            self.find_earliest_fifo_pipe_dat_arr_B.append(find_earliest_fifo_pipe_dat)

            cur_level = Gearbox_level(env, line_clk_period, sys_clk_period, self.granularity_list[index], self.fifo_size_list[index], \
                self.enq_pipe_cmd_arr_B[index], self.enq_pipe_sts_arr_B[index], self.deq_pipe_req_arr_B[index], self.deq_pipe_dat_arr_B[index], \
                self.find_earliest_fifo_pipe_req_arr_B[index], self.find_earliest_fifo_pipe_dat_arr_B[index], \
                self.fifo_r_in_pipe_matrix_B[index], self.fifo_r_out_pipe_matrix_B[index], \
                self.fifo_w_in_pipe_matrix_B[index], self.fifo_w_out_pipe_matrix_B[index], \
                fifo_write_latency=1, fifo_read_latency=1, fifo_check_latency=1, fifo_num=10, initial_vc=0)

            self.levelsB.append(cur_level)
            
            index = index + 1'''
        
        
        # Tracking last pkt enque level
        self.prev_enq_level_lst = [0] * 4    # We have 4 flows (flow id) in the simulation
        # TODO: Peixuan 04212021 flow table to do
        
        # initiate ping-pong indicator (level_ping_pong_arr[index] = is level[index] serving set A?)
        #self.level_ping_pong_arr = []
        #index = 0
        #while (index < self.level_num):
        #    self.level_ping_pong_arr.append(True)
        #    index = index + 1
        
        # initiate vc
        self.virtrul_clock = initial_vc

        print("Initialized Gearbox II Proto I")

        print("[Gearbox II debug] level number = {}".format(len(self.levelsA)))

        self.run()
    
    def run(self):
        self.env.process(self.enque_p())
        self.env.process(self.deque_p())
        self.env.process(self.find_earliest_non_empty_level_fifo_p())
        #self.env.process(self.jump_vc_p())
    
    def enque_p(self):
        # enque process
        while True:
            pkt = yield self.gb_enq_pipe_cmd.get() 
            pkt_finish_time = pkt.get_finish_time(False)
            tuser = pkt.get_tuser()
            flow_id = tuser.pkt_id[0]

            yield self.wait_sys_clks(self.enque_latency) # 02232021 Peixuan: enque delay
            # find the correct level to enque
            insert_level = self.find_insert_level(pkt_finish_time)
            
            if insert_level == -1:
                # level > max level
                self.gb_enq_pipe_sts.put(0) # pkt overflow
                print("[Gearbox] enque pkt overflow, exceeds highest level")
                self.drop_pipe.put((pkt.hdr_addr, pkt.meta_addr, pkt.tuser))
                self.gb_enq_pipe_sts.put(False)
            else:
                #current_fifo_index = self.levelsA[insert_level].cur_fifo
                #fifo_index_offset = self.find_enque_index_offset(insert_level, pkt_finish_time) # find enque fifo index offset (from cur_fifo)
                #if (current_fifo_index + fifo_index_offset) < self.fifo_num_list[insert_level]:
                #    enque_index = current_fifo_index + fifo_index_offset                                        # find enque fifo index
                #else:
                #    enque_index = current_fifo_index + fifo_index_offset - self.fifo_num_list[insert_level]     # find enque fifo index
                #self.enq_pipe_cmd_arr_A[insert_level].put((pkt, enque_index))                   # submit enque request
                self.enq_pipe_cmd_arr_A[insert_level].put(pkt)                   # submit enque request
                (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_A[insert_level].get()
                self.pkt_cnt = self.pkt_cnt + 1
                self.gb_enq_pipe_sts.put(True) # enque successfully
                #print("[Gearbox] pkt {} enque level {}, fifo {}".format(pkt.get_uid(), insert_level, enque_index))
                print("[Gearbox] pkt {} enque level {}".format(pkt.get_uid(), insert_level))

            '''elif insert_level == self.level_num-1:
                # level = max level
                # For top level: only enque current Set A
                current_fifo_index = self.levelsA[insert_level].cur_fifo
                fifo_index_offset = self.find_enque_index_offset(insert_level, pkt_finish_time) # find enque fifo index offset (from cur_fifo)
                if (current_fifo_index + fifo_index_offset) < self.fifo_num_list[insert_level]:
                    enque_index = current_fifo_index + fifo_index_offset                                        # find enque fifo index
                else:
                    enque_index = current_fifo_index + fifo_index_offset - self.fifo_num_list[insert_level]     # find enque fifo index
                self.enq_pipe_cmd_arr_A[insert_level].put((pkt, enque_index))                   # submit enque request
                (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_A[insert_level].get()
                self.pkt_cnt = self.pkt_cnt + 1
                self.gb_enq_pipe_sts.put(True) # enque successfully
                print("[Gearbox] pkt {} enque level {}, fifo {}".format(pkt.get_uid(), insert_level, enque_index))




            else:
                # level < max level
                if insert_level > self.prev_enq_level_lst[flow_id]:
                    self.prev_enq_level_lst[flow_id] = insert_level # update prev_enq_level
                else:
                    insert_level = self.prev_enq_level_lst[flow_id] # if last_enq_level >= insert level, enque last_enq_level

                fifo_index_offset = self.find_enque_index_offset(insert_level, pkt_finish_time)
                current_fifo_index = 0
                if (self.level_ping_pong_arr[insert_level] == True):
                    # Current serving set A
                    current_fifo_index = self.levelsA[insert_level].cur_fifo
                else:
                    # Current serving set B
                    current_fifo_index = self.levelsB[insert_level].cur_fifo
                
                # based on the current fifo and fifo offest, find out if this pkt enqur current set or next set
                enque_current_set = ((current_fifo_index + fifo_index_offset) < self.fifo_num_list[insert_level])
                
                # 01262021 Peixuan debug
                print("[Gearbox Debug]: enque_current_set = {}, current_fifo_index = {}, fifo_index_offset = {} ".format(enque_current_set, current_fifo_index, fifo_index_offset))

                if (((self.level_ping_pong_arr[insert_level] == True) and enque_current_set)):
                    # Case 01: Enque current Set A
                    enque_index = current_fifo_index + fifo_index_offset
                    self.enq_pipe_cmd_arr_A[insert_level].put((pkt, enque_index))
                    (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_A[insert_level].get()
                    print("[Gearbox] pkt {} enque level {} A, fifo {}".format(pkt.get_uid(), insert_level, enque_index))
                elif (((self.level_ping_pong_arr[insert_level] == False) and enque_current_set)):
                    # Case 02: Enque current Set B
                    enque_index = current_fifo_index + fifo_index_offset
                    self.enq_pipe_cmd_arr_B[insert_level].put((pkt, enque_index))
                    (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_B[insert_level].get()
                    print("[Gearbox] pkt {} enque level {} B, fifo {}".format(pkt.get_uid(), insert_level, enque_index))
                elif (((self.level_ping_pong_arr[insert_level] == True) and not enque_current_set)):
                    # Case 02: Enque next Set B
                    enque_index =  current_fifo_index + fifo_index_offset - self.fifo_num_list[insert_level]
                    self.enq_pipe_cmd_arr_B[insert_level].put((pkt, enque_index))
                    (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_B[insert_level].get()
                    print("[Gearbox] pkt {} enque level {} A, fifo {}".format(pkt.get_uid(), insert_level, enque_index))
                else:
                    # Case 02: Enque next Set A
                    enque_index =  current_fifo_index + fifo_index_offset - self.fifo_num_list[insert_level]
                    self.enq_pipe_cmd_arr_A[insert_level].put((pkt, enque_index))
                    (popped_pkt_valid, popped_pkt) = yield self.enq_pipe_sts_arr_A[insert_level].get()
                    print("[Gearbox] pkt {} enque level {} B, fifo {}".format(pkt.get_uid(), insert_level, enque_index))
                
                self.pkt_cnt = self.pkt_cnt + 1
                self.gb_enq_pipe_sts.put(True) # enque successfully'''
                
    
    def deque_p(self):
        # deque process
        while True:
            yield self.gb_deq_pipe_req.get()
            print("[Gearbox Debug] Starting deque at VC = {}".format(self.vc))

            yield self.wait_sys_clks(self.deque_01_latency) # 02232021 Peixuan: deque delay 01 (regular deque delay for every deque)

            (dequed_pkt, if_reload) = (0, False)

            # if no pkt, loop when new pkt arrives
            while (dequed_pkt == 0):

                print ("[Gearbox Debug] Gearbox II pkt_cnt: {} ".format(self.pkt_cnt))

                deque_level_index = self.find_deque_level()

                #while deque_level_index == -1:
                #    print("[GearboxII] No pkt to serve for now")            
            
                if deque_level_index == 0:
                    # deque from base level
                    print("[Gearbox II] Deque from base level")
                    level_cur_fifo = self.levelsA[deque_level_index].cur_fifo
                    self.find_earliest_fifo_pipe_req_arr_A[deque_level_index].put(level_cur_fifo)
                    dequed_fifo = yield self.find_earliest_fifo_pipe_dat_arr_A[deque_level_index].get()
                    if dequed_fifo == -1:
                        print("[GearboxII] Error, all fifos are empty")
                    else:
                        print ("[GearboxII Debug] dequeing level {} A, fifo {}".format(deque_level_index, dequed_fifo))
                        self.deq_pipe_req_arr_A[deque_level_index].put(dequed_fifo)
                        (dequed_pkt, if_reload) = yield self.deq_pipe_dat_arr_A[deque_level_index].get()
                else:
                    # deque from levels with pifo
                    # deque from pifo, no fifo index required
                    print ("[Gearbox Debug] dequeing level {} A, pifo".format(deque_level_index))
                    self.deq_pipe_req_arr_A[deque_level_index].put(-1) # no deque fifo index required
                    (dequed_pkt, if_reload) = yield self.deq_pipe_dat_arr_A[deque_level_index].get()
            
            self.pkt_cnt = self.pkt_cnt - 1     # update pkt_cnt
            # return pkt
            self.gb_deq_pipe_dat.put((dequed_pkt, 0))

            print ("[Gearbox Debug] deque pkt: {} , if_reload: {}".format(dequed_pkt, if_reload))

            vc_to_update = dequed_pkt.get_finish_time(debug=False)
            if vc_to_update > self.vc:
                # update vc now
                self.update_vc(vc_to_update)



            '''while deque_level_index == -1:
                # No bytes to serve in this round, move to the next one
                print("[Gearbox] Finished serving all levelsm move to next round")
                yield self.wait_sys_clks(self.deque_02_latency) # 02232021 Peixuan: deque delay 02 (extra deque delay to update VC)
                #self.print_debug_info() # 01262021 Peixuan debug
                self.print_level_pkt_cnt() # 02032021 Peixuan debug
                # Run round until not return -1
                #self.run_round()
                # 02022021 updated vc by jumping
                self.gb_update_VC_req.put(1)
                print("[Gearbox Debug] put gb_update_VC_req here @ VC = {}".format(self.vc))
                updated_vc = yield self.gb_update_VC_dat.get()
                print("[Gearbox Debug] found updated VC = {} @ VC = {}".format(updated_vc, self.vc))
                #updated_vc = self.jump_vc()
                self.update_vc(updated_vc)
                deque_level_index = self.find_deque_level()
                print ("[Gearbox] deque_level_index = {}".format(deque_level_index))
                
            if self.level_ping_pong_arr[deque_level_index]:
                # Serve set A in ping-pong fifos
                dequed_fifo = self.levelsA[deque_level_index].cur_fifo
                print ("[Gearbox Debug] dequeing level {} A, fifo {}".format(deque_level_index, dequed_fifo))
                self.deq_pipe_req_arr_A[deque_level_index].put(dequed_fifo)
                (dequed_pkt, if_reload) = yield self.deq_pipe_dat_arr_A[deque_level_index].get()
            else:
                # Serve set B in ping-pong fifos
                dequed_fifo = self.levelsB[deque_level_index].cur_fifo
                print ("[Gearbox Debug] dequeing level {} B, fifo {}".format(deque_level_index, dequed_fifo))
                self.deq_pipe_req_arr_B[deque_level_index].put(dequed_fifo)
                (dequed_pkt, if_reload) = yield self.deq_pipe_dat_arr_B[deque_level_index].get()

            # Update served bytes
            self.deque_served_bytes[deque_level_index] = self.deque_served_bytes[deque_level_index] + dequed_pkt.get_bytes() # TODO get pkt len
            self.pkt_cnt = self.pkt_cnt - 1     # update pkt_cnt

            # return pkt
            self.gb_deq_pipe_dat.put((dequed_pkt, 0))'''
    
    # Private        
    
    def find_enque_index_offset(self, level_index, finish_time):
        # We need to find which fifo to enque at Gearbox level
        fifo_index_offset = math.floor(float(finish_time) / self.granularity_list[level_index]) - math.floor(float(self.vc) / self.granularity_list[level_index])

        if fifo_index_offset < 0:
            fifo_index_offset = 0 # if pkt's finish time has passed, enque the current fifo
        # we need to first use the granularity to round up vc and pkt.finish_time to calculate the fifo offset
        return fifo_index_offset   
    
    
    '''def find_deque_level(self):
        # find the level to serve based on the self.deque_bytes[index] (bytes to deque) and self.deque_served_bytes[index] (dequed bytes)
        index = 0
        while (index < self.level_num):
            if self.deque_bytes[index] > self.deque_served_bytes[index]:
                is_fifo_empty = self.is_level_cur_fifo_empty(index) # skip if this fifo is already empty
                if not is_fifo_empty:
                    return index
            index = index + 1
        return -1 # If all level has been served, return -1'''
    

    def find_deque_level(self):
        # find the level to serve based on the self.deque_bytes[index] (bytes to deque) and self.deque_served_bytes[index] (dequed bytes)
        min_finish_time = 99999999  # TODO: we need a large inital value
        while (min_finish_time == 99999999): # TODO: find non-empty level until there is one non-empty level
            index = 0
            deque_level = 0
            earliset_pkt = self.blevel.peek_earliest_pkt()
            if earliset_pkt == 0:
                print("No pkt in level {}".format(index))
            else:
                earliest_pkt = self.blevel.peek_earliest_pkt()
                if earliest_pkt == 0:
                    print("No pkt in level {}".format(index + 1))
                else:
                    min_finish_time = earliest_pkt.get_finish_time(debug=False)
            #index = index + 1
            while (index < self.level_num - 1):
                print("[Gearbox II debug: ] Check earliest pkt in level {}".format(index))
                earliest_pkt = self.levelsA[index].peek_earliest_pkt()
                if earliest_pkt == 0:
                    print("No pkt in level {}".format(index + 1))
                else:
                    level_min_ft = earliest_pkt.get_finish_time(debug=False)
                    if level_min_ft < min_finish_time:
                        min_finish_time = level_min_ft
                        deque_level = index
                index = index + 1
        
        return deque_level

    
    '''def run_round(self):
        # this fuction updated VC by 1
        # We need to update self.level_ping_pong_arr if we finish serving one set
        updated_vc = self.vc + 1
        self.vc = updated_vc
        print("[Gearbox] run round, current vc = {}".format(self.vc))

        # Update ping-pong
        # based on the updated VC value, we can calculate which set to serve in each level
        index = 0
        while (index < self.level_num):
            serve_set_A = (math.floor(float(updated_vc) / (self.granularity_list[index] * self.fifo_num_list[index])) % 2 == 0)
            self.level_ping_pong_arr[index] = serve_set_A
            print("[Gearbox] updated level {} is serve A = {}".format(index, serve_set_A))
            index = index + 1

        # for each level to find current serving fifos
        index = 0
        while (index < self.level_num - 1):     # The highest level don't have AB ping pong level
            # update level vc
            (level_vc, is_new_fifo_A) = self.levelsA[index].update_vc(self.vc) # update_vc will return (vc, is_updated)
            (level_vc, is_new_fifo_B) = self.levelsB[index].update_vc(self.vc)

            if (self.level_ping_pong_arr[index] == True):
                cur_fifo = self.levelsA[index].get_cur_fifo()
                cur_fifo_index = self.levelsA[index].cur_fifo
            else:
                cur_fifo = self.levelsB[index].get_cur_fifo()
                cur_fifo_index = self.levelsB[index].cur_fifo
            
            if index == 0:
                deque_byte = cur_fifo.get_bytes() # Level 0 serve the entire fifo
            else:
                deque_byte = (float(self.granularity_list[0])/self.granularity_list[index]) * math.ceil(float(cur_fifo_index+1)/self.fifo_num_list[index]) * cur_fifo.get_bytes() # TODO we need to implement get_bytes() function in FIFO
            
            self.deque_bytes[index] = deque_byte
            print("[Gearbox] updated level {} serve bytes = {}".format(index, deque_byte))
            self.deque_served_bytes[index] = 0

            index = index + 1
        
        # update top level deque bytes
        
        cur_fifo = self.levelsA[index].get_cur_fifo()
        cur_fifo_index = self.levelsA[index].cur_fifo
        deque_byte = (float(self.granularity_list[0])/self.granularity_list[index]) * math.ceil(float(cur_fifo_index+1)/self.fifo_num_list[index]) * cur_fifo.get_bytes() # TODO we need to implement get_bytes() function in FIFO        
        self.deque_bytes[index] = deque_byte
        print("[Gearbox] updated level {} serve bytes = {}".format(index, deque_byte))
        self.deque_served_bytes[index] = 0
        # Update vc to outside
        self.vc_data_pipe.put(self.vc)'''

    def update_vc(self, updated_vc):
        # this fuction updated VC to input updated_vc
        # We need to update self.level_ping_pong_arr if we finish serving one set
                
        self.vc = updated_vc
        print("[Gearbox] <update_vc> run round, current vc = {}".format(self.vc))

        # Update ping-pong
        # based on the updated VC value, we can calculate which set to serve in each level
        #index = 0
        '''while (index < self.level_num):
            serve_set_A = (math.floor(float(updated_vc) / (self.granularity_list[index] * self.fifo_num_list[index])) % 2 == 0)
            self.level_ping_pong_arr[index] = serve_set_A
            print("[Gearbox] <update_vc> updated level {} is serve A = {}".format(index, serve_set_A))
            index = index + 1'''

        # for each level to find current serving fifos
        index = 0
        self.blevel.update_vc(self.vc)          # update vc of the base level

        while (index < self.level_num - 1):     # The highest level don't have AB ping pong level
            # update level vc
            (level_vc, is_new_fifo_A) = self.levelsA[index].update_vc(self.vc) # update_vc will return (vc, is_updated)
            #(level_vc, is_new_fifo_B) = self.levelsB[index].update_vc(self.vc)

            '''if (self.level_ping_pong_arr[index] == True):
                cur_fifo = self.levelsA[index].get_cur_fifo()
                cur_fifo_index = self.levelsA[index].cur_fifo
            else:
                cur_fifo = self.levelsB[index].get_cur_fifo()
                cur_fifo_index = self.levelsB[index].cur_fifo
            
            if index == 0:
                deque_byte = cur_fifo.get_bytes() # Level 0 serve the entire fifo
            else:
                deque_byte = (float(self.granularity_list[0])/self.granularity_list[index]) * math.ceil(float(cur_fifo_index+1)/self.fifo_num_list[index]) * cur_fifo.get_bytes() # TODO we need to implement get_bytes() function in FIFO
            
            self.deque_bytes[index] = deque_byte
            print("[Gearbox] <update_vc> updated level {} serve bytes = {}".format(index, deque_byte))
            self.deque_served_bytes[index] = 0'''

            index = index + 1
        
        # start to migrate each level
        index = 1                               # starting from level 1 (not base level 0)
        while (index < self.level_num - 1):     # from level 1 to top level
            (level_vc, is_new_fifo_A) = self.levelsA[index].update_vc(self.vc)
            self.mig_pipe_req_arr_A[index].put(self.levelsA[index].cur_fifo)    # start from the updated cur_fifo
            index = index + 1
        
        # update top level deque bytes
        
        '''cur_fifo = self.levelsA[index].get_cur_fifo()
        cur_fifo_index = self.levelsA[index].cur_fifo
        deque_byte = (float(self.granularity_list[0])/self.granularity_list[index]) * math.ceil(float(cur_fifo_index+1)/self.fifo_num_list[index]) * cur_fifo.get_bytes() # TODO we need to implement get_bytes() function in FIFO        
        self.deque_bytes[index] = deque_byte
        print("[Gearbox] <update_vc> updated level {} serve bytes = {}".format(index, deque_byte))
        self.deque_served_bytes[index] = 0'''
        # Update vc to outside
        self.vc_data_pipe.put(self.vc)

    
    '''def jump_vc_p(self):
        # jump to next non-empty vc
        while True:
            yield self.gb_update_VC_req.get()
            print("[Gearbox Debug] <jump_vc_p>: Starting to find jump VC")

            #(level_index, fifo_index, is_current_set) = self.find_earliest_non_empty_level_fifo()
            self.gb_jump_VC_req.put(1)
            #(level_index, fifo_index, is_current_set) = yield self.gb_jump_VC_dat.get()
            (updated_vc, level_index, fifo_index, is_set_A) = yield self.gb_jump_VC_dat.get()

            while level_index == -1:
                # all empty, not update vc
                #(level_index, fifo_index, is_current_set) = self.find_earliest_non_empty_level_fifo()
                print("[Gearbox Debug] <jump_vc_p>: All levels are empty")
                self.gb_jump_VC_req.put(1)
                #(level_index, fifo_index, is_current_set) = yield self.gb_jump_VC_dat.get()
                (updated_vc, level_index, fifo_index, is_set_A) = yield self.gb_jump_VC_dat.get()

            #return updated_vc
            self.gb_update_VC_dat.put(updated_vc)'''
        

    def find_earliest_non_empty_level_fifo_p(self):
        while True:
            yield self.gb_jump_VC_req.get()
            level = 0
            #updated_vc = float('inf')   # initialized as infinity
            updated_vc = 999999999999   # initialized as infinity
            has_non_empty_fifo = False  # if we found any non-empty fifo, set this flag as True

            # debug usage
            debug_level_index = -1
            debug_fifo_index = -1
            debug_is_setA = False

            # get max vc of the earliest non-empty fifo in each level each set
            while (level < self.level_num - 1):
                # set A:
                cur_set = False
                if(self.level_ping_pong_arr[level]):
                    # if current serving level A in this level
                    cur_fifo = self.levelsA[level].cur_fifo
                    cur_set = True
                else:
                    cur_fifo = 0
                    cur_set = False
                
                self.find_earliest_fifo_pipe_req_arr_A[level].put(cur_fifo)
                earlest_fifo_idex = yield self.find_earliest_fifo_pipe_dat_arr_A[level].get()
                if not earlest_fifo_idex == -1:
                    # found a non-empty fifo
                    has_non_empty_fifo = True

                    # cur_fifo_index in cur_set in this level
                    jump_index_offset = 0
                    level_cur_fifo = math.floor(self.vc/self.granularity_list[level]) % self.fifo_num_list[level]
                    if (cur_set):
                        jump_index_offset = earlest_fifo_idex - level_cur_fifo
                    else:
                        jump_index_offset = earlest_fifo_idex + self.fifo_num_list[level] - level_cur_fifo

                    #max_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]

                    min_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]

                    #if not (level == 0):
                    #    # if not level 0, jump to the end of this fifo, that's max vc for this fifo
                    #    max_vc = max_vc + self.granularity_list[level] - 1
                        
                    #if (max_vc < updated_vc):
                    if (min_vc < updated_vc):
                        #updated_vc = max_vc
                        updated_vc = min_vc
                        # debug usage
                        debug_level_index = level
                        debug_fifo_index = earlest_fifo_idex
                        debug_is_setA = True
                    

                # set B:
                cur_set = False
                if not (self.level_ping_pong_arr[level]):
                    # if current serving level B in this level
                    cur_fifo = self.levelsB[level].cur_fifo
                    cur_set = True
                else:
                    cur_fifo = 0
                    cur_set = False
                
                self.find_earliest_fifo_pipe_req_arr_B[level].put(cur_fifo)
                earlest_fifo_idex = yield self.find_earliest_fifo_pipe_dat_arr_B[level].get()
                if not earlest_fifo_idex == -1:
                    # found a non-empty fifo
                    has_non_empty_fifo = True

                    # cur_fifo_index in cur_set in this level
                    jump_index_offset = 0
                    level_cur_fifo = math.floor(self.vc/self.granularity_list[level]) % self.fifo_num_list[level]
                    if (cur_set):
                        jump_index_offset = earlest_fifo_idex - level_cur_fifo
                    else:
                        jump_index_offset = earlest_fifo_idex + self.fifo_num_list[level] - level_cur_fifo

                    #max_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]
                    min_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]

                    #if not (level == 0):
                    #    # if not level 0, jump to the end of this fifo, that's max vc for this fifo
                    #    max_vc = max_vc + self.granularity_list[level] - 1
                        
                    #if (max_vc < updated_vc):
                    #    updated_vc = max_vc
                    if (min_vc < updated_vc):
                        updated_vc = min_vc
                        # debug usage
                        debug_level_index = level
                        debug_fifo_index = earlest_fifo_idex
                        debug_is_setA = False
                
                level = level + 1
                
            # Top level only have set A

            # set A:
            cur_fifo = self.levelsA[level].cur_fifo
            self.find_earliest_fifo_pipe_req_arr_A[level].put(cur_fifo)
            earlest_fifo_idex = yield self.find_earliest_fifo_pipe_dat_arr_A[level].get()
            if not earlest_fifo_idex == -1:
                # found a non-empty fifo
                has_non_empty_fifo = True
                jump_index_offset = 0
                level_cur_fifo = math.floor(self.vc/self.granularity_list[level]) % self.fifo_num_list[level]
                jump_index_offset = earlest_fifo_idex - level_cur_fifo
                
            #max_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]
            min_vc = (math.floor(self.vc/self.granularity_list[level]) + jump_index_offset) * self.granularity_list[level]

            #max_vc = max_vc + self.granularity_list[level] - 1
                        
            #if (max_vc < updated_vc):
            #    updated_vc = max_vc
            if (min_vc < updated_vc):
                updated_vc = min_vc
                # debug usage
                debug_level_index = level
                debug_fifo_index = earlest_fifo_idex
                debug_is_setA = True
            
            if (self.vc + 1) > updated_vc:
                updated_vc = self.vc + 1

            if (has_non_empty_fifo):
                self.gb_jump_VC_dat.put((updated_vc, debug_level_index, debug_fifo_index, debug_is_setA)) #updated_vc, level index, fifo index, is set A
                print("[Gearbox debug] <find_earliest_non_empty_level_fifo_p> Found non-empty fifo in level: {} , is set A: {}, fifo: {}, updated vc = {}".format(debug_level_index, debug_is_setA, debug_fifo_index, updated_vc))
            else:
                self.gb_jump_VC_dat.put((self.vc, -1, -1, debug_is_setA)) #updated_vc, level index, fifo index, is set A
                print("[Gearbox debug] <find_earliest_non_empty_level_fifo_p> Not Found non-empty fifo")
    

    
    def find_insert_level(self, finish_time):
        # insert_level: the insert level of last packet in the flow
        # find the correct level to enque
        index = 0
        while (index < self.level_num):
            level_max_vc = (math.floor(self.vc/self.granularity_list[index]) + self.fifo_num_list[index]) * self.granularity_list[index]
            if finish_time < level_max_vc:
                return index
            index = index + 1
        return -1 # pkt overflow
    
    def get_pkt_cnt(self):
        return self.pkt_cnt

    def is_level_cur_fifo_empty(self, level_index):
        if self.level_ping_pong_arr[level_index]:
            # Serve set A in ping-pong fifos
            cur_fifo_index = self.levelsA[level_index].cur_fifo
            cur_fifo = self.levelsA[level_index].fifos[cur_fifo_index]
        else:
            # Serve set B in ping-pong fifos
            cur_fifo_index = self.levelsB[level_index].cur_fifo
            cur_fifo = self.levelsB[level_index].fifos[cur_fifo_index]
        size = cur_fifo.get_bytes()
        return size == 0
        
        
    
    # Peixuan's temp debug function
    def print_debug_info(self):
        print("Current VC = {}".format(self.vc))
        print("Current Gearbox pkt_cnt = {}".format(self.pkt_cnt)) # Peixuan debug
        index = 0
        while(index < self.level_num - 1):
            print("Level {}".format(index))
            print("is serving set A: {}".format(self.level_ping_pong_arr[index]))
            print("Level {} Set A, pkt_cnt: {}".format(index, self.levelsA[index].get_pkt_cnt()))
            print("Level {} Set B, pkt_cnt: {}".format(index, self.levelsB[index].get_pkt_cnt()))

            index = index + 1
        print("Level {}".format(index))
        print("Level {} Set A, pkt_cnt: {}".format(index, self.levelsA[index].get_pkt_cnt()))

    def print_level_pkt_cnt(self):
        print("<print_level_pkt_cnt> Current VC = {}".format(self.vc))
        print("<print_level_pkt_cnt> Current Gearbox pkt_cnt = {}".format(self.pkt_cnt)) # Peixuan debug
        index = 0
        while(index < self.level_num - 1):
            print("<print_level_pkt_cnt> Level {}".format(index))
            print("<print_level_pkt_cnt> is serving set A: {}".format(self.level_ping_pong_arr[index]))
            print("<print_level_pkt_cnt> Level {} Set A, pkt_cnt: {}".format(index, self.levelsA[index].get_pkt_cnt()))
            if not (self.levelsA[index].get_pkt_cnt() == 0):
                fifo_index = 0
                while(fifo_index < self.fifo_num_list[index]):
                    print("<print_level_pkt_cnt> FIFO {} pkt cnt: {}".format(fifo_index, self.levelsA[index].fifos[fifo_index].get_len()))
                    fifo_index = fifo_index + 1
            print("<print_level_pkt_cnt> Level {} Set B, pkt_cnt: {}".format(index, self.levelsB[index].get_pkt_cnt()))
            if not (self.levelsB[index].get_pkt_cnt() == 0):
                fifo_index = 0
                while(fifo_index < self.fifo_num_list[index]):
                    print("<print_level_pkt_cnt> FIFO{} pkt cnt: {}".format(fifo_index, self.levelsB[index].fifos[fifo_index].get_len()))
                    fifo_index = fifo_index + 1
            index = index + 1
        print("<print_level_pkt_cnt> Level {}".format(index))
        print("<print_level_pkt_cnt> Level {} Set A, pkt_cnt: {}".format(index, self.levelsA[index].get_pkt_cnt()))
        if not (self.levelsA[index].get_pkt_cnt() == 0):
            fifo_index = 0
            while(fifo_index < self.fifo_num_list[index]):
                print("<print_level_pkt_cnt> FIFO{} pkt cnt: {}".format(fifo_index, self.levelsA[index].fifos[fifo_index].get_len()))
                fifo_index = fifo_index + 1



        
    