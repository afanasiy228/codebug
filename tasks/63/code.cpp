#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    long long s=0;
    for(int i=0;i<n/2;i++) s+=a[i];
    long long total=0;
    for(long long x:a) total+=x;

    cout<<llabs(total-2*s)<<"\n";

}
