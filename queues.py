from hwsim_utils import *

class FIFO(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe=None, maxsize=128, write_latency=1, read_latency=1, init_items=[]):
        super(FIFO, self).__init__(env, line_clk_period, sys_clk_period)
        self.r_in_pipe = r_in_pipe
        self.r_out_pipe = r_out_pipe
        self.w_in_pipe = w_in_pipe
        self.w_out_pipe = w_out_pipe
        self.write_latency = write_latency
        self.read_latency = read_latency
        self.maxsize = maxsize
        self.items = init_items # do we still need this
        self.bytes = 0

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.push_sm())
        self.env.process(self.pop_sm())

    def push_sm(self):
        """
        State machine to push incoming data into the FIFO
        """
        while True:
            # wait to receive incoming data
            data = yield self.w_in_pipe.get()
            # model write latency
            yield self.wait_sys_clks(self.write_latency)
            # try to write data into FIFO
            if len(self.items) < self.maxsize:
                self.items.append(data)
                self.bytes = self.bytes + data.get_bytes() # we assume data here is packet
            else:
                print >> sys.stderr, "ERROR: FIFO push_sm: FIFO full, cannot push {}".format(data)
            # indicate write_completion
            if self.w_out_pipe is not None:
                done = 1
                self.w_out_pipe.put(done)

    def pop_sm(self):
        """
        State machine to pop data out of the FIFO upon request
        """
        while True:
            # wait to receive a read request
            req = yield self.r_in_pipe.get()
            # model read latency
            yield self.wait_sys_clks(self.read_latency)
            # try to read head element
            if len(self.items) > 0:
                data = self.items[0]
                self.items = self.items[1:]
                self.bytes = self.bytes - data.get_bytes() # we assume data here is packet
            else:
                print >> sys.stderr, "ERROR: FIFO pop_sm: attempted to read from empty FIFO"
                data = None
            # write data back
            self.r_out_pipe.put(data)

    def __str__(self):
        return str(self.items)

    # TODO: get_len()? is_empty()?

    def get_len(self):
        return len(self.items)
    
    def get_bytes(self):
        return self.bytes
    
    def peek_front(self):
        if not len(self.items) == 0:
            return self.items[0]
        else:
            return 0
    


# Peixuan 10292020
class PIFO(HW_sim_object):
    def __init__(self, env, line_clk_period, sys_clk_period, r_in_pipe, r_out_pipe, w_in_pipe, w_out_pipe=None, maxsize=128, write_latency=1, read_latency=1, shift_latency=1, init_items=[]):
        super(PIFO, self).__init__(env, line_clk_period, sys_clk_period)
        self.r_in_pipe = r_in_pipe
        self.r_out_pipe = r_out_pipe
        self.w_in_pipe = w_in_pipe
        self.w_out_pipe = w_out_pipe
        self.write_latency = write_latency
        self.read_latency = read_latency
        self.shift_latency = shift_latency
        self.maxsize = maxsize
        self.items = init_items

        # register processes for simulation
        self.run()

    def run(self):
        self.env.process(self.push_sm())
        self.env.process(self.pop_sm())

    def push_sm(self):
        """
        State machine to push incoming data into the PIFO
        """
        popped_data = 0

        while True:
            popped_data_valid = 0
            # wait to receive incoming data
            data = yield self.w_in_pipe.get()
            # model write latency
            yield self.wait_sys_clks(self.write_latency)
            # first enque the item
            self.items.append(data)
            # then insert in the correct position and shift (sorting)
            yield self.wait_sys_clks(self.shift_latency)
            self.items = sorted(self.items, key=lambda pkt: pkt.get_finish_time(debug=False))
            if len(self.items) > self.maxsize : # Peixuan Q: what if len = maxsize, should we keep the data?
                popped_data = self.items.pop(len(self.items)-1)
                popped_data_valid = 1
            # indicate write_completion
            if self.w_out_pipe is not None:
                #if popped_data:
                #    self.w_out_pipe.put(popped_data)
                #    print ('popped_data: {0}'.format(popped_data))
                #else:
                    done = 1
                    self.w_out_pipe.put((done, popped_data, popped_data_valid)) # tuple

    def pop_sm(self):
        """
        State machine to pop data out of the PIFO upon request
        """
        while True:
            # wait to receive a read request
            req = yield self.r_in_pipe.get()
            # model read latency
            yield self.wait_sys_clks(self.read_latency)
            # try to read head element
            if len(self.items) > 0:
                data = self.items[0]
                self.items = self.items[1:]
            else:
                print >> sys.stderr, "ERROR: PIFO pop_sm: attempted to read from empty PIFO"
                data = None
            # write data back
            self.r_out_pipe.put(data)

    def __str__(self):
        return str(self.items)
    
    def peek_front(self):
        if not len(self.items) == 0:
            return self.items[0]
        else:
            return 0

    def peek_tail(self):
        if not len(self.items) == 0:
            return self.items[len(self.items) - 1]
        else:
            return 0