#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    long long n;
    if(!(cin>>n)) return 0;
    long long r = sqrt((long double)n);

    if(r*r<n) r++;

    cout<<r<<"\n";

}
