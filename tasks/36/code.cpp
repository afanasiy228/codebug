#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,S;
    if(!(cin>>n>>S)) return 0;
    vector<int> c(n);
    for(int i=0;i<n;i++) cin>>c[i];

    const int INF=1e9;
    vector<int> dp(S+1, INF);
    dp[0]=0;

    for(int i=0;i<n;i++) {

        for(int s=S;s>=c[i];s--) {

            dp[s]=min(dp[s], dp[s-c[i]]+1);

        }

    }

    cout<<(dp[S]>=INF?-1:dp[S])<<"\n";

}
