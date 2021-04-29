import math
from hwsim_utils import *
from packet import Packet_descriptior
from queues import FIFO, PIFO

# Peixuan 11122020
# This is the base level (level 0), no pifo
class GearboxII_level(HW_sim_object):
    # Public
    def __init__(self, env, line_clk_period, sys_clk_period, granularity, \
                 fifo_size, pifo_size, pifo_threshold, \
                 enq_pipe_cmd, enq_pipe_sts, deq_pipe_req, deq_pipe_dat, \
                 rld_pipe_cmd, rld_pipe_sts, mig_pipe_req, mig_pipe_dat, mig_enq_pipe_cmd, mig_enq_pipe_sts, \
                 gb_enq_pipe_cmd, gb_enq_pipe_sts, \
                 find_earliest_fifo_pipe_req, find_earliest_fifo_pipe_dat, \
                 fifo_r_in_pipe_arr, fifo_r_out_pipe_arr, fifo_w_in_pipe_arr, fifo_w_out_pipe_arr, \
                 pifo_r_in_pipe, pifo_r_out_pipe, pifo_w_in_pipe, pifo_w_out_pipe, \
                 fifo_write_latency=1, fifo_read_latency=1, fifo_check_latency=1, fifo_num=10, pifo_write_latency=1, pifo_read_latency=1, pifo_shift_latency=1, initial_vc=0):
                 
        super(GearboxII_level, self).__init__(env, line_clk_period, sys_clk_period)
        self.granularity = granularity      # Level Grabularuty, units of VC
        self.fifo_num = fifo_num            # Level fifo num
        self.fifo_size = fifo_size          # Level fifo size, all the fifos in a level has the same size
        self.pifo_size = pifo_size          # Level pifo size
        self.pifo_threshold = pifo_threshold# Lecel pifo threshold
        self.enq_pipe_cmd = enq_pipe_cmd    # Level enque pipe input 
        self.enq_pipe_sts = enq_pipe_sts    # Level enque pipe output
        self.deq_pipe_req = deq_pipe_req    # Level deque pipe input
        self.deq_pipe_dat = deq_pipe_dat    # Level deque pipe output
        self.rld_pipe_cmd = rld_pipe_cmd    # Level reload pipe input 
        self.rld_pipe_sts = rld_pipe_sts    # Level reload pipe output
        self.mig_pipe_req = mig_pipe_req    # Level migration pipe input
        self.mig_pipe_dat = mig_pipe_dat    # Level migration pipe output
        self.mig_enq_pipe_cmd = mig_enq_pipe_cmd    # Level migration enque pipe input 
        self.mig_enq_pipe_sts = mig_enq_pipe_sts    # Level migration enque pipe output
        self.gb_enq_pipe_cmd = gb_enq_pipe_cmd  # migration re-circulation enque cmd
        self.gb_enq_pipe_sts = gb_enq_pipe_sts  # migration re-circulation enque sts
        self.find_earliest_fifo_pipe_req = find_earliest_fifo_pipe_req      # depreciated
        self.find_earliest_fifo_pipe_dat = find_earliest_fifo_pipe_dat      # depreciated
        # fifo read/write latency (of each fifo)
        self.fifo_read_latency = fifo_read_latency
        self.fifo_write_latency = fifo_write_latency
        self.fifo_check_latency = fifo_check_latency    # depreciated
        self.pifo_read_latency = pifo_read_latency
        self.pifo_write_latency = pifo_write_latency
        self.pifo_shift_latency = pifo_shift_latency

        self.pifo_max_time = 100000000 # TODO: set a large PIFO max time (when PIFO is empty, should set a large pifo_max_time)

        self.fifos = []     # fifo array

        # Initialize PIFO array and read/write pipe
        
        self.pifo_r_in_pipe = pifo_r_in_pipe
        self.pifo_r_out_pipe = pifo_r_out_pipe
        self.pifo_w_in_pipe = pifo_w_in_pipe
        self.pifo_w_out_pipe = pifo_w_out_pipe

        self.pifo = PIFO(env, line_clk_period, sys_clk_period, \
                         self.pifo_r_in_pipe, self.pifo_r_out_pipe, \
                         self.pifo_w_in_pipe, self.pifo_w_out_pipe, \
                         self.pifo_size, self.pifo_write_latency, self.pifo_read_latency, self.pifo_shift_latency, init_items=[])

        # Initialize VC

        self.vc = initial_vc
        self.cur_fifo = math.floor(self.vc / self.granularity) % self.fifo_num  # find current fifo (by VC and granularity)

        # Initialize pkt cnt
        self.pkt_cnt = 0
        
        # Initialize FIFO array and read/write pipe array
        
        self.fifo_r_in_pipe_arr = fifo_r_in_pipe_arr
        self.fifo_r_out_pipe_arr = fifo_r_out_pipe_arr
        self.fifo_w_in_pipe_arr = fifo_w_in_pipe_arr
        self.fifo_w_out_pipe_arr = fifo_w_out_pipe_arr
        
        index = 0
        while (index < self.fifo_num):
            init_items = []
            # creat each fifo and append to fifo array
            new_fifo = FIFO(env, line_clk_period, sys_clk_period, self.fifo_r_in_pipe_arr[index], self.fifo_r_out_pipe_arr[index], \
                self.fifo_w_in_pipe_arr[index], self.fifo_w_out_pipe_arr[index], self.fifo_size, \
                    self.fifo_write_latency, self.fifo_read_latency, init_items)
            self.fifos.append(new_fifo) 

            index = index + 1
            
        self.run()

    def run(self):
        self.env.process(self.enqueue_p())  # enque process
        self.env.process(self.dequeue_p())  # deque process
        self.env.process(self.find_earliest_non_empty_fifo_p()) # depreciated
        self.env.process(self.mig_enqueue_p())
        self.env.process(self.migration_p())
        self.env.process(self.reload_p())

    # Public

    #def deque_fifo(self, fifo_index):
    #    # TODO: Peixuan 0409
    
    def peek_earliest_pkt(self):
        top_pkt = self.pifo.peek_front()
        return top_pkt

    
    def find_earliest_non_empty_fifo_p(self):   # depreciated        
        while True:
            index = yield self.find_earliest_fifo_pipe_req.get() # fifo index, find the earliest non-empty fifo from this fifo
            print ('[Level] Check earliest fifo from index {}'.format(index))
            #yield self.wait_sys_clks(self.fifo_check_latency) # 02232021 Peixuan: put this delay elsewhere
            non_empty_fifo_index = self.check_non_empty_fifo(index)
            print ('[Level] Found earliest fifo index = {}'.format(non_empty_fifo_index))
            self.find_earliest_fifo_pipe_dat.put(non_empty_fifo_index)

    
    def check_non_empty_fifo(self, index):
        cur_index = index
        while cur_index < self.fifo_num:
            if not self.fifos[cur_index].get_len() == 0:
                self.find_earliest_fifo_pipe_dat.put(cur_index)
                print ('[Level] Found earliest fifo{}'.format(cur_index))
                return cur_index
            cur_index = cur_index + 1
        print ('[Level] All fifos are empty')
        return -1

    
    def enqueue_p(self):
        # enque process
        # enque includes queue index to enque
        while True:
            (pkt) = yield self.enq_pipe_cmd.get() 
            if not pkt == 0:
                if pkt.get_finish_time(debug=False) < self.pifo_max_time:
                    # TODO enque PIFO
                    self.pifo_w_in_pipe.put(pkt)
                    (done, popped_pkt, popped_pkt_valid) = yield self.pifo_w_out_pipe.get()
                    self.pifo_max_time = self.pifo.peek_tail().get_finish_time(debug=False) # update pifo_max_time

                    # recycle popped_pkt FIFO
                    if popped_pkt_valid == 1:
                        enque_fifo_index = self.get_enque_fifo(popped_pkt.get_finish_time(debug=False)) # get recycle fifo index
                        self.fifo_w_in_pipe_arr[enque_fifo_index].put(popped_pkt)
                        yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                        print("[Level] pkt {} recycled to fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    
                    self.enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
                else:
                    enque_fifo_index = self.get_enque_fifo(pkt.get_finish_time(debug=False))
                    # enque FIFO
                    self.fifo_w_in_pipe_arr[enque_fifo_index].put(pkt)
                    yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                    print("[Level] pkt {} enqued fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    self.enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
            else:
                print("[Level] Illegal packet")
    
    def mig_enqueue_p(self):
        # enque process
        # enque includes queue index to enque
        while True:
            (pkt) = yield self.mig_enq_pipe_cmd.get() 
            if not pkt == 0:
                if pkt.get_finish_time(debug=False) < self.pifo_max_time:
                    # TODO enque PIFO
                    self.pifo_w_in_pipe.put(pkt)
                    (done, popped_pkt, popped_pkt_valid) = yield self.pifo_w_out_pipe.get()
                    self.pifo_max_time = self.pifo.peek_tail().get_finish_time(debug=False) # update pifo_max_time

                    # recycle popped_pkt FIFO
                    if popped_pkt_valid == 1:
                        enque_fifo_index = self.get_enque_fifo(popped_pkt.get_finish_time(debug=False)) # get recycle fifo index
                        self.fifo_w_in_pipe_arr[enque_fifo_index].put(popped_pkt)
                        yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                        print("[Level] pkt {} recycled to fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    
                    self.enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
                else:
                    enque_fifo_index = get_enque_fifo(pkt.get_finish_time(debug=False))
                    # enque FIFO
                    self.fifo_w_in_pipe_arr[enque_fifo_index].put(pkt)
                    yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                    print("[Level] mig: pkt {} enqued fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    self.mig_enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
            else:
                print("[Level] Illegal packet")
    
    
    
    '''def enqueue_p(self):
        # enque process
        # enque includes queue index to enque
        while True:
            (pkt, enque_fifo_index) = yield self.enq_pipe_cmd.get() 
            if not pkt == 0:
                if pkt.get_finish_time() < self.pifo_max_time:
                    # TODO enque PIFO
                    self.pifo_w_in_pipe.put(pkt)
                    popped_pkt = yield self.pifo_w_out_pipe.get()
                    self.pifo_max_time = self.pifo.peek_tail().get_finish_time() # update pifo_max_time

                    # recycle popped_pkt FIFO
                    # TODO: need to get recycle index
                    self.fifo_w_in_pipe_arr[enque_fifo_index].put(popped_pkt)
                    yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                    print("[Level] pkt {} recycled to fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    self.enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
                else:
                    # enque FIFO
                    self.fifo_w_in_pipe_arr[enque_fifo_index].put(pkt)
                    yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                    print("[Level] pkt {} enqued fifo {}".format(pkt.get_uid(), enque_fifo_index))
                    self.enq_pipe_sts.put((0, 0))
                    self.pkt_cnt = self.pkt_cnt + 1 # update level pkt cnt
            else:
                print("[Level] Illegal packet")'''

    def dequeue_p(self):
        # deque process (only deque PIFO)
        while True:
            yield self.deq_pipe_req.get()
            if self.deq_pipe_dat is not None:
                self.pifo_r_in_pipe.put(1)
                dequed_pkt = yield self.pifo_r_out_pipe.get()
                if_reload = 0
                if self.pifo.get_len() < self.pifo_threshold:
                    # need to reload now
                    if_reload = 1
                    self.rld_pipe_cmd.put(1) # TODO Peixuan not sure if this works
                self.deq_pipe_dat.put((dequed_pkt, if_reload))
                self.pkt_cnt = self.pkt_cnt - 1 # update level pkt cnt
    
    def migration_p(self):
        # migration process (deque FIFO)
        while True:
            index = yield self.mig_pipe_req.get()
            mig_num = self.fifos[index].get_len()
            if self.mig_pipe_dat is not None:
                mig_index = 0
                while mig_index < mig_num:
                    self.fifo_r_in_pipe_arr[index].put(1)
                    migrated_pkt = yield self.fifo_r_out_pipe_arr[index].get()
                    self.mig_pipe_dat.put((migrated_pkt, 0))
                    
                    # recirculate back to gearbox enque pipe
                    self.gb_enq_pipe_cmd.put(migrated_pkt)
                    yield self.gb_enq_pipe_sts.get()

                    self.pkt_cnt = self.pkt_cnt - 1 # update level pkt cnt
                    mig_index = mig_index + 1
    
    def reload_p(self):
        # reload process (deque FIFO enque PIFO)
        while True:
            # deque FIFO[index]
            #index = yield self.rld_pipe_cmd.get()
            yield self.rld_pipe_cmd.get()
            cur_fifo_index = self.cur_fifo
            index = (cur_fifo_index + 1) % self.fifo_num
            self.find_earliest_fifo_pipe_req.put(index)
            index = yield self.find_earliest_fifo_pipe_dat.get()

            pkt_to_reload = self.fifos[index].get_len() # get current fifo size
            pkt_reloaded  = 0   # initialized as 0
            if self.rld_pipe_dat is not None:
                while pkt_reloaded < pkt_to_reload:
                    pkt_reloaded = pkt_reloaded + 1
                    self.fifo_r_in_pipe_arr[index].put(1)
                    reload_pkt = yield self.fifo_r_out_pipe_arr[index].get()

                    # enque PIFO
                    self.pifo_w_in_pipe.put(pkt)
                    (done, popped_pkt, popped_pkt_valid) = yield self.pifo_w_out_pipe.get()
                    self.pifo_max_time = self.pifo.peek_tail().get_finish_time(debug=False) # update pifo_max_time

                    # recycle popped_pkt FIFO
                    if popped_pkt_valid == 1:
                        enque_fifo_index = self.get_enque_fifo(popped_pkt.get_finish_time(debug=False)) # get recycle fifo index
                        self.fifo_w_in_pipe_arr[enque_fifo_index].put(popped_pkt)
                        yield self.fifo_w_out_pipe_arr[enque_fifo_index].get()
                        print("[Level] during reloading: {} recycled to fifo {}".format(pkt.get_uid(), enque_fifo_index))

                if self.pifo.get_len() < self.pifo_threshold:
                    self.rld_pipe_sts.put((0, 1)) # succefully finished reloading, need to reload more pkts
                else:
                    self.rld_pipe_sts.put((0, 0)) # succefully finished reloading, don't need to reload more pkts
            else:
                self.rld_pipe_sts.put((-1, -1)) # error in reloading


    def update_vc(self, vc):
        # Update vc
        if self.vc < vc:
            self.vc = vc
        # update current serving fifo
        old_fifo = self.cur_fifo
        if self.fifos[self.cur_fifo].get_len() == 0:
            self.cur_fifo = math.floor(self.vc / self.granularity) % self.fifo_num       
        
        is_new_fifo = not (old_fifo==self.cur_fifo)
        return (self.vc, is_new_fifo) # to see if the cur_fifo is updated
    
    def get_vc(self):
        return self.vc
    
    def get_cur_fifo(self):
        return self.fifos[self.cur_fifo]
    
    def get_pkt_cnt(self):
        return self.pkt_cnt
    
    def get_enque_fifo(self, finish_time):
        current_fifo_index = self.cur_fifo
        fifo_index_offset = math.floor(float(finish_time) / self.granularity) - math.floor(float(self.vc) / self.granularity)
        if fifo_index_offset < 0:
            fifo_index_offset = 0 # if pkt's finish time has passed, enque the current fifo

        enque_index = 0

        if (current_fifo_index + fifo_index_offset) < self.fifo_num:
            enque_index = current_fifo_index + fifo_index_offset                    # find enque fifo index
        else:
            enque_index = current_fifo_index + fifo_index_offset - self.fifo_num    # find enque fifo index

        return enque_index