#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,k;
    if(!(cin>>n>>k)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    long long ans = *max_element(a.begin(), a.end());

    cout<<ans<<"\n";

}
