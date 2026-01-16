#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long x1,y1,x2,y2,x,y;
    if(!(cin>>x1>>y1>>x2>>y2>>x>>y)) return 0;

    long long xmin=min(x1,x2), xmax=max(x1,x2);
    long long ymin=min(y1,y2), ymax=max(y1,y2);

    if(x>xmin && x<xmax && y>ymin && y<ymax) cout<<"YES\n";
    else cout<<"NO\n";

}
