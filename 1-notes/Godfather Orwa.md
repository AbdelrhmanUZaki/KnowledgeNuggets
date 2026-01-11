---
tags:
  - web-pt
---
1. Check out-of-scope websites for data leaks and JS files (don't test, it's forbidden).
    - You might find credentials, and if successful, log in to an in-scope website ⇒ auth bypass P1.
2. Perform `GitHub`, [Shodan.io](<https://shodan.io>) reconnaissance, and `Google Dorking`

- The Org name you found in step 3 below, search using it at the recon stage.
    - helpful tools
        - https://dorks.faisalahmed.me/
        - https://github.com/TakSec/google-dorks-bug-bounty
        - https://abhijithb200.github.io/investigator/

1. Use [crt.sh](http://crt.sh/) to find domains/sub-domains.
    - How to know if the domains/sub-domains you found belong to the organization?
        - There are some ways
            1. Check the page footer to see if they wrote it.
                
            2. Alternatively, use the method shown below.
                
                [Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/c61482e1-264a-4e26-a54b-a37bc1cb6e17/Untitled.mp4)
                
            3. [https://www.sslshopper.com/ssl-checker.html](https://www.sslshopper.com/ssl-checker.html)
                
            4. [https://who.is/](https://who.is/) -it won’t always give you information-
                
1. While using [](https://shodan.io/)[https://shodan.io](https://shodan.io), you are limited to just seeing the first 2 pages from the results. You could create more free accounts to get more data
    1. Try these dorks on Shodan
        - ssl:”program name”
            
        - [Ssl.cert.subject.CN](http://ssl.cert.subject.cn/):”” 200
            
        - http.title:”Grafana” 200
            
            - If there is a new CVE, you could do this, filter with org names like this, and search for your preferred programs:
                
                [Shodan Facet Analysis](https://www.shodan.io/search/facet?query=http.title:%E2%80%9DGrafana%E2%80%9D+200&facet=org)
                
        - http.title:"Citrix Gateway"200