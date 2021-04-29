import math
from hwsim_utils import *
from packet import Packet_descriptior
from queues import FIFO, PIFO

# Peixuan 11122020
# This is the base level (level 0), no pifo
class Base_level(HW_sim_object):
    # Public
    def __init__(self, env, line_clk_period, sys_clk_period, granularity, fifo_size, \
                 enq_pipe_cmd, enq_pipe_sts, deq_pipe_req, deq_pipe_dat, drop_pipe,\
                 find_earliest_fifo_pipe_req, find_earliest_fifo_pipe_dat, \
                 fifo_r_in_pipe_arr, fifo_r_out_pipe_arr, fifo_w_in_pipe_arr, fifo_w_out_pipe_arr, \
                 vc_upd_pipe, \
                 fifo_write_latency=1, fifo_read_latency=1, fifo_check_latency=1, fifo_num=10, initial_vc=0):
                 
        super(Base_level, self).__init__(env, line_clk_period, sys_clk_period)
        self.granularity = granularity
        self.fifo_num = fifo_num
        self.fifo_size = fifo_size
        self.enq_pipe_cmd = enq_pipe_cmd
        self.enq_pipe_sts = enq_pipe_sts
        self.deq_pipe_req = deq_pipe_req
        self.deq_pipe_dat = deq_pipe_dat
        self.drop_pipe = drop_pipe
        self.find_earliest_fifo_pipe_req = find_earliest_fifo_pipe_req
        self.find_earliest_fifo_pipe_dat = find_earliest_fifo_pipe_dat
        self.fifo_read_latency = fifo_read_latency
        self.fifo_write_latency = fifo_write_latency
        self.fifo_check_latency = fifo_check_latency

        self.enque_latency = 2                       # 02272021 Peixuan: total enque latency = enque_latency + write latency
        self.deque_latency = 2                       # 02272021 Peixuan: total enque latency = deque_latency + read latency

        self.fifos = []

        # Initialize VC

        self.vc = initial_vc
        self.cur_fifo = math.floor(self.vc / self.granularity) % self.fifo_num

        # Initialize pkt cnt
        self.pkt_cnt = 0

        # Peixuan debug counter
        self.vc_fall_behind_cnt = 0
        
        # Initialize FIFO array and read/write handle
        
        self.fifo_r_in_pipe_arr = fifo_r_in_pipe_arr
        self.fifo_r_out_pipe_arr = fifo_r_out_pipe_arr
        self.fifo_w_in_pipe_arr = fifo_w_in_pipe_arr
        self.fifo_w_out_pipe_arr = fifo_w_out_pipe_arr

        self.vc_upd_pipe = vc_upd_pipe
        
        index = 0
        while (index < self.fifo_num):
            #self.fifo_r_in_pipe_arr.append(simpy.Store(env))
            #self.fifo_r_out_pipe_arr.append(simpy.Store(env))
            #self.fifo_w_in_pipe_arr.append(simpy.Store(env))
            #self.fifo_w_out_pipe_arr.append(simpy.Store(env))
            init_items = []
            
            new_fifo = FIFO(env, line_clk_period, sys_clk_period, self.fifo_r_in_pipe_arr[index], self.fifo_r_out_pipe_arr[index], \
                self.fifo_w_in_pipe_arr[index], self.fifo_w_out_pipe_arr[index], self.fifo_size, \
                    self.fifo_write_latency, self.fifo_read_latency, init_items)
            self.fifos.append(new_fifo) 

            index = index + 1
            
        self.run()

    def run(self):
        self.env.process(self.enqueue_p())
        self.env.process(self.dequeue_p())
        self.env.process(self.find_earliest_non_empty_fifo_p())
        self.env.process(self.top_tb()) # blevel vc update
        self.env.process(self.mig_enqueue_p())

    # Public
    
    def find_earliest_non_empty_fifo_p(self):        
        while True:
            index = yield self.find_earliest_fifo_pipe_req.get() # fifo index, find the earliest non-empty fifo from this fifo
            print ('Check earliest fifo from index {}'.format(index))
            yield self.wait_sys_clks(self.fifo_check_latency)
            cur_index = index            
            while True:
                if not self.fifos[cur_index].get_len() == 0:
                    self.find_earliest_fifo_pipe_dat.put(cur_index)
                    print ('Found earliest fifo{}'.format(cur_index))
                    break
                cur_index = cur_index + 1
                if (cur_index == self.fifo_num):
                    # recirculate if go to the back of the level
                    cur_index = 0
                if (cur_index == index):
                    self.find_earliest_fifo_pipe_dat.put(-1) # this means all the fifos are empty
                    print ('All fifos are empty')
                    break


    def enqueue_p(self):
#    def enque(self, pkt):
        while True:
            pkt = yield self.enq_pipe_cmd.get()
            yield self.wait_sys_clks(self.enque_latency) # 02272021 Peixuan: enque delay 
            if not pkt == 0:
                fifo_index_offset = math.floor(pkt.get_finish_time(debug=False) / self.granularity) - math.floor(self.vc / self.granularity)
                if fifo_index_offset < 0:
                    fifo_index_offset = 0 # if pkt's finish time has passed, enque the current fifo
                # we need to first use the granularity to round up vc and pkt.finish_time to calculate the fifo offset
                if fifo_index_offset > self.fifo_num: # ignore the pkt if overflow
                    print("fifo_index_offset = {}".format(fifo_index_offset))
                    print("fifo num = {}".format(self.fifo_num))
                    #print("pkt ovfl: Rx rank: {} flow_id: {} pkt_num: {}".format(pkt.tuser.rank, pkt.tuser.pkt_id[0], pkt.tuser.pkt_id[1]))
                    print("@VC = {}, pkt ovfl: Rx rank: {} flow_id: {} pkt_num: {}".format(self.vc, pkt.tuser.rank, pkt.tuser.pkt_id[0], pkt.tuser.pkt_id[1]))
                    self.drop_pipe.put((pkt.hdr_addr, pkt.meta_addr, pkt.tuser))
                    self.enq_pipe_sts.put((0, 0))
                    continue
                enque_fifo_index = (self.cur_fifo + fifo_index_offset) % self.fifo_num
                print("Enq: @ VC = {}, pkt with rank {} enqueued fifo {}".format(self.vc, pkt.get_finish_time(debug=False), enque_fifo_index)) # Peixuan debug
                if (self.vc > pkt.get_finish_time(debug=False)):                            # Peixuan debug
                    self.vc_fall_behind_cnt = self.vc_fall_behind_cnt + 1                   # Peixuan debug
                    print("System fall behind VC cnt: {}".format(self.vc_fall_behind_cnt))  # Peixuan debug
                self.fifo_w_in_pipe_arr[enque_fifo_index].put(pkt)
                yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                #self.enq_pipe_sts.put(1)
                self.enq_pipe_sts.put((0, 0))
                self.pkt_cnt = self.pkt_cnt + 1
            else:
                print("Illegal packet")

    """
    def deque_fifo(self, fifo_index):
        # deque packet from sepecific fifo, when migrating packets
        print ("deque_fifo {}".format(fifo_index))
        self.fifo_r_in_pipe_arr[fifo_index].put(1) 
        print ("requested pkt from fifo {}".format(fifo_index))
        dequed_pkt = yield self.fifo_r_out_pipe_arr[fifo_index].get()
        print ("dequeued pkt {} from fifo {}".format(dequed_pkt, fifo_index))
        return dequed_pkt
    """
    
    '''def get_earliest_pkt_timestamp(self): # TODO: this is put into higher level
        # return time stamp from the head of PIFO
        if self.fifos[self.cur_fifo].get_len():
            top_pkt = self.fifos[self.cur_fifo].peek_front()
            return top_pkt.get_finish_time()
        else:
            earliest_fifo = self.find_next_non_empty_fifo(self.cur_fifo)
            if earliest_fifo > -1:
                top_pkt = self.fifos[earliest_fifo].peek_front()
                return top_pkt.get_finish_time()
            else:
                return -1 # there is no pkt in this level'''

    def dequeue_p(self):
        # request includes queue index to deque:
        # queue_index = -1: PIFO
        # queue_index >= 0: FIFO
        while True:
            index = yield self.deq_pipe_req.get()
            yield self.wait_sys_clks(self.deque_latency) # 02232021 Peixuan: enque delay
            if index == -1: 
                # deque PIFO
                print("Error: No PIFO in the base level")
            else: 
                # deque FIFO[index]
                if self.deq_pipe_dat is not None:
                    self.fifo_r_in_pipe_arr[index].put(1)
                    dequed_pkt = yield self.fifo_r_out_pipe_arr[index].get()
                    self.deq_pipe_dat.put((dequed_pkt, 0))
                    self.pkt_cnt = self.pkt_cnt - 1


    def update_vc(self, vc):
        # Update vc
        if self.vc < vc:
            self.vc = vc
        # update current serving fifo
        if self.fifos[self.cur_fifo].get_len() == 0:
            self.cur_fifo = math.floor(self.vc / self.granularity) % self.fifo_num       
        print("updated blevel vc = {}".format(self.vc)) # Peixuan debug
        print("@VC = {} , updated blevel vc = {}".format(self.vc, self.vc)) # Peixuan debug
        return self.vc
    
    def get_vc(self):
        return self.vc
    
    def get_cur_fifo(self):
        return self.cur_fifo
    
    def get_pkt_cnt(self):
        return self.pkt_cnt
    
    def top_tb(self):
        while True:
            updated_vc = yield self.vc_upd_pipe.get()
            self.vc = updated_vc
            print("updated blevel vc = {}".format(self.vc)) # Peixuan debug
    
    def peek_earliest_pkt(self):
        # TODO: return earliest pkt in the base level
        traverse_index = 0
        fifo_index = self.cur_fifo
        while traverse_index < self.fifo_num:
            if self.fifos[fifo_index].get_len() > 0:
                return self.fifos[fifo_index].peek_front()
            traverse_index = traverse_index + 1
            fifo_index = fifo_index + 1
        return -1   # all fifos are empty
        