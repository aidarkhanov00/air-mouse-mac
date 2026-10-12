import unittest
from controller import Controller

class Mouse:
    def __init__(self): self.events=[]
    def position(self): return (300,200)
    def moveTo(self,*p): self.events.append(('move',p))
    def click(self): self.events.append(('click',))
    def mouseDown(self): self.events.append(('down',))
    def mouseUp(self): self.events.append(('up',))
    def scroll(self,n): self.events.append(('scroll',n))

def sample(pinch=.8, fingers=(True,False,False,False), y=.5):
    return dict(pinch=pinch,fingers=fingers,pointer=(.5,y))

class Tests(unittest.TestCase):
    def setUp(self):
        self.mouse=Mouse(); self.c=Controller(self.mouse,1440,900)
    def arm(self):
        self.c.toggle(); self.c.update(0,sample()); self.c.update(.4,sample())
    def test_paused_never_controls(self):
        self.c.update(0,sample()); self.assertEqual(self.mouse.events,[])
    def test_click_once_on_release(self):
        self.arm(); self.c.update(.5,sample(.1)); self.c.update(.7,sample())
        self.c.update(.8,sample()); self.assertEqual(self.mouse.events.count(('click',)),1)
        self.assertNotIn(('down',),self.mouse.events)
    def test_drag_and_release(self):
        self.arm(); self.c.update(.5,sample(.1)); self.c.update(1.1,sample(.1))
        self.c.update(1.2,sample()); self.assertEqual(self.mouse.events.count(('down',)),1)
        self.assertEqual(self.mouse.events.count(('up',)),1)
        self.assertNotIn(('click',),self.mouse.events)
    def test_loss_releases_without_click(self):
        self.arm(); self.c.update(.5,sample(.1)); self.c.update(1.1,sample(.1)); self.c.update(1.2,None)
        self.assertFalse(self.c.down); self.assertIn(('up',),self.mouse.events)
        self.assertNotIn(('click',),self.mouse.events)
    def test_unarmed_pinch_no_click(self):
        self.c.toggle(); self.c.update(0,sample(.1)); self.c.update(.2,sample())
        self.assertNotIn(('click',),self.mouse.events)
    def test_pause_releases_drag(self):
        self.arm(); self.c.update(.5,sample(.1)); self.c.update(1.1,sample(.1)); self.c.toggle()
        self.assertFalse(self.c.active); self.assertFalse(self.c.down)
    def test_scroll_does_not_move_cursor(self):
        self.c.toggle(); self.c.update(0,sample(fingers=(1,1,0,0)))
        self.c.update(.1,sample(fingers=(1,1,0,0),y=.3))
        self.assertTrue(any(e[0]=='scroll' for e in self.mouse.events))
        self.assertFalse(any(e[0]=='move' for e in self.mouse.events))
    def test_fist_stops(self):
        self.arm(); self.mouse.events.clear(); self.c.update(.5,sample(fingers=(0,0,0,0)))
        self.assertEqual(self.mouse.events,[])

if __name__=='__main__': unittest.main()
