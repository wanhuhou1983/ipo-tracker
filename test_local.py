import sys
sys.stdout.reconfigure(encoding='utf-8')
import spider

try:
    d = spider.get_cb_new(90)
    with open('c:/Users/linhu/WorkBuddy/20260421211906/test_result.txt', 'w', encoding='utf-8') as f:
        f.write(f"CB: {len(d)}\n")
        d2 = spider.get_ipo_china(90)
        f.write(f"IPO: {len(d2)}\n")
        d3 = spider.get_reits()
        f.write(f"REITs: {len(d3)}\n")
        f.write("OK\n")
except Exception as e:
    with open('c:/Users/linhu/WorkBuddy/20260421211906/test_result.txt', 'w', encoding='utf-8') as f:
        f.write(f"ERROR: {e}\n")
