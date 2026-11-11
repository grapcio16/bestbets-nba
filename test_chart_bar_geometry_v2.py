"""Regression tests for compact, centered SVG bars on responsive BestBets V2.

Run with: python -m unittest -v test_chart_bar_geometry_v2.py
Uses the *actual generated JS helper* and Node; no NBA calls or credentials.
"""
import json
import re
import shutil
import subprocess
import unittest


class ResponsiveChartBars(unittest.TestCase):
    def test_generated_javascript_uses_compact_bar_geometry(self):
        from bestbets_v2_preview import JS
        self.assertIn("const {step,bar,start}=chartBarGeometry(w,n);", JS)
        self.assertIn("x=padLeft+start+step*i+(step-bar)/2", JS)
        self.assertNotIn("const bar=Math.min(46,(w-gap*(n-1))/n),step=w/n", JS)
        self.assertIn("Math.min(13,Math.max(9,step*.17))", JS)
        self.assertIn("Math.min(11,Math.max(8,step*.14))", JS)

    @unittest.skipUnless(shutil.which("node"), "Node.js needed to evaluate actual chart layout helper")
    def test_five_ten_and_twenty_game_bars_are_compact_and_centered(self):
        from bestbets_v2_preview import JS
        helper = re.search(
            r"function chartBarGeometry\(available,count\)\{[\s\S]*?\n\}",
            JS,
        )
        self.assertIsNotNone(helper)
        samples = [[1130,5],[1130,10],[1130,15],[1130,20],
                   [650,5],[650,10],[280,5],[280,10],[210,20]]
        script = helper.group(0) + """
const out = %s.map(([w,n]) => {
  const layout=chartBarGeometry(w,n), {plotSpan,step,bar,start}=layout;
  const first=start+(step-bar)/2;
  const last=start+step*(n-1)+(step-bar)/2+bar;
  return {w,n,plotSpan,step,bar,start,first,last};
});
console.log(JSON.stringify(out));
""" % json.dumps(samples)
        completed = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, timeout=8, check=True,
        )
        values = json.loads(completed.stdout)
        for v in values:
            self.assertGreater(v["bar"], 0)
            self.assertLessEqual(v["bar"], v["step"])
            self.assertGreaterEqual(v["first"], 0)
            self.assertLessEqual(v["last"], v["w"] + 1e-6)
            self.assertAlmostEqual(v["first"] + v["last"], v["w"], delta=1e-6)
            self.assertLessEqual(v["step"] - v["bar"], 35)
            self.assertLessEqual(v["plotSpan"], 960)
        l5=next(v for v in values if v["w"]==1130 and v["n"]==5)
        l10=next(v for v in values if v["w"]==1130 and v["n"]==10)
        l20=next(v for v in values if v["w"]==1130 and v["n"]==20)
        self.assertEqual(l5["plotSpan"],480)
        self.assertEqual(l10["plotSpan"],960)
        self.assertEqual(l20["plotSpan"],960)
        self.assertEqual(l5["step"],96)
        self.assertEqual(l10["step"],96)

if __name__=="__main__":
    unittest.main()
