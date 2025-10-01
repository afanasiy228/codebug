#include <iostream>
#include <vector>
#include <iomanip>
#include <cmath>
#include <bitset>

using namespace std;

#define int long long

#define db long double


db a(db a, db b, db c, db d) {
  return a * d - b * c;
}
 
db triangleArea(db x1, db y1, db x2, db y2) {
  return abs(a(x1, y1, x2, y2));
}


signed main() {
  ios::sync_with_stdio(0);
  cin.tie(0);
  cout.tie(0);

  cout << setprecision(10) << fixed;

  int x1,y1,x2,y2,x3,y3;
  cin >> x1 >> y1 >> x2 >> y2 >> x3 >> y3 ;

  cout << triangleArea(x2 - x1,y2 - y1,x3 - x2,y3 - y2);
}