#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a,b,c,d,e,f,g,h,i;
    if(!(cin>>a>>b>>c>>d>>e>>f>>g>>h>>i)) return 0;

    long long det = a*(e*i - f*h) + b*(d*i - f*g) + c*(d*h - e*g);

    cout<<det<<"\n";

}
