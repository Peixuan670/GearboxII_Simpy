class Packet_descriptior:
    # Tuser + headpointer as pkt
    def __init__(self, hdr_addr, meta_addr, tuser):
        self.hdr_addr = hdr_addr
        self.meta_addr = meta_addr
        self.tuser = tuser
    
    def get_finish_time(self, debug): # rank
        tuser = self.tuser
        if debug:
            print("tuser = {}".format(tuser))
        return tuser.rank
        #return self.tuser.rank
    
    def set_finish_time(self, finish_time):
        self.tuser.rank = finish_time
    
    def get_hdr_addr(self): # head ptr
        return self.hdr_addr
    
    def get_meta_addr(self): # head ptr
        return self.meta_addr
    
    def get_uid(self):
        return self.tuser.pkt_id
    
    def get_tuser(self):
        return self.tuser

    def get_bytes(self):
        return self.tuser.pkt_len