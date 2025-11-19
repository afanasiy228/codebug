#include <iostream>
#include <vector>
#include <iomanip>
#include <cmath>
#include <bitset>

using namespace std;
#define int long long
#define db long double

const db PI = 3.14159265358980;





db d(db x1, db y1, db x2, db y2) {
  return sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
}
 

db point_to_line(db cx, db cy, db ax, db ay, db bx, db by) {
  return abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / d(ax, ay, bx, by);
}

db point_to_ray(db cx, db cy, db ax, db ay, db bx, db by) {
  db abx = bx - ax, aby = by - ay;
  db acx = cx - ax, acy = cy - ay;
 
  
  return point_to_line(cx, cy, ax, ay, bx, by);
}



signed main() {
  ios::sync_with_stdio(0);
  cin.tie(0);
  cout.tie(0);

  cout << setprecision(10) << fixed;

  db x1,y1,x2,y2,x3,y3;
  cin >> x1 >> y1 >> x2 >> y2 >> x3 >> y3;



  cout << (point_to_ray(x1,y1,x2,y2,x3,y3) == 0 ? "YES" : "NO");
}